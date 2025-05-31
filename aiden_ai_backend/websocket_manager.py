import asyncio
import json
import redis.asyncio as aioredis # Use async version of redis library
from fastapi import WebSocket
from typing import Dict, Set, Optional # Added Optional

# Redis connection details (ideally from environment variables in a real app)
REDIS_HOST = "localhost"
REDIS_PORT = 6379
# Example Redis URL: "redis://localhost:6379/0"

# Global redis client instances, to be initialized on app startup
redis_publisher: Optional[aioredis.Redis] = None
redis_subscriber_connection: Optional[aioredis.Redis] = None

async def init_redis_pool():
    global redis_publisher, redis_subscriber_connection
    try:
        # Using a connection pool is generally recommended for managing connections.
        pool = aioredis.ConnectionPool.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}/0", decode_responses=False)
        redis_publisher = aioredis.Redis(connection_pool=pool)
        redis_subscriber_connection = aioredis.Redis(connection_pool=pool)

        # Test connection
        await redis_publisher.ping()
        await redis_subscriber_connection.ping()
        print("Successfully connected to Redis and initialized publisher/subscriber clients.")
    except Exception as e:
        print(f"Error connecting to Redis or initializing clients: {e}")
        redis_publisher = None
        redis_subscriber_connection = None


class ConnectionManager:
    def __init__(self):
        self.local_active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, conversation_id: str):
        await websocket.accept()
        if conversation_id not in self.local_active_connections:
            self.local_active_connections[conversation_id] = set()
        self.local_active_connections[conversation_id].add(websocket)
        print(f"WebSocket connected: {websocket.client.host}:{websocket.client.port} to conv {conversation_id} (local count: {len(self.local_active_connections[conversation_id])})")


    def disconnect(self, websocket: WebSocket, conversation_id: str):
        if conversation_id in self.local_active_connections:
            if websocket in self.local_active_connections[conversation_id]:
                self.local_active_connections[conversation_id].remove(websocket)
                print(f"WebSocket disconnected: {websocket.client.host}:{websocket.client.port} from conv {conversation_id} (local count: {len(self.local_active_connections[conversation_id]) if conversation_id in self.local_active_connections and self.local_active_connections[conversation_id] else 0})")
                if not self.local_active_connections[conversation_id]: # Check if set is empty
                    del self.local_active_connections[conversation_id]
                    print(f"Conversation {conversation_id} has no more local connections.")

    async def broadcast_to_conversation_locally(self, message_payload: dict, conversation_id: str):
        if conversation_id in self.local_active_connections:
            message_str = json.dumps(message_payload)
            connections_to_send = list(self.local_active_connections[conversation_id])

            for connection in connections_to_send:
                try:
                    await connection.send_text(message_str)
                except Exception as e:
                    print(f"Error sending to a websocket in conv {conversation_id} (client: {connection.client}), removing: {e}")
                    self.disconnect(connection, conversation_id)


    async def publish_message_to_redis(self, message_payload: dict, conversation_id: str):
        if not redis_publisher:
            print("Redis publisher not initialized! Cannot publish message.")
            return

        channel_name = f"chat:{conversation_id}"
        try:
            message_str = json.dumps(message_payload)
            await redis_publisher.publish(channel_name, message_str)
            print(f"Message published to Redis channel {channel_name}")
        except Exception as e:
            print(f"Error publishing message to Redis channel {channel_name}: {e}")

manager = ConnectionManager() # Global instance of the manager for this server instance

# Background task for subscribing to Redis channels and forwarding messages
async def redis_message_subscriber():
    if not redis_subscriber_connection:
        print("Redis subscriber connection not initialized! Subscriber task cannot start.")
        return

    # Check initial connection
    try:
        await redis_subscriber_connection.ping()
        print("Redis subscriber connection confirmed.")
    except Exception as e:
        print(f"Redis subscriber connection failed ping: {e}. Subscriber task cannot start.")
        return

    pubsub = redis_subscriber_connection.pubsub()

    try:
        await pubsub.psubscribe("chat:*")
        print("Redis subscriber task started, psubscribed to 'chat:*'")

        while True:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "pmessage":
                    channel_name_bytes = message["channel"]
                    channel_name = channel_name_bytes.decode('utf-8') if isinstance(channel_name_bytes, bytes) else channel_name_bytes

                    if not channel_name.startswith("chat:"): # Defensive check
                        print(f"Received message on unexpected channel: {channel_name}")
                        continue

                    conversation_id = channel_name.split(":", 1)[1]

                    message_data_bytes = message["data"]
                    message_data_str = message_data_bytes.decode('utf-8') if isinstance(message_data_bytes, bytes) else message_data_bytes

                    try:
                        message_payload = json.loads(message_data_str)
                        print(f"Redis subscriber received on {channel_name}, broadcasting locally to conv {conversation_id}")
                        await manager.broadcast_to_conversation_locally(message_payload, conversation_id)
                    except json.JSONDecodeError:
                        print(f"Error decoding JSON from Redis channel {channel_name}: {message_data_str}")
                    except Exception as e_proc:
                        print(f"Error processing message from Redis channel {channel_name}: {e_proc}")
            except asyncio.TimeoutError:
                pass # Expected to allow loop to check for cancellation or other conditions
            except aioredis.exceptions.ConnectionError as e_conn: # More specific exception for redis
                print(f"Redis subscriber connection error: {e_conn}. Attempting to re-establish pubsub...")
                await asyncio.sleep(5)
                try: # Try to re-establish pubsub
                    await pubsub.punsubscribe("chat:*") # Clean up old subscription first
                    await pubsub.psubscribe("chat:*")
                    print("Re-subscribed to 'chat:*' after connection error.")
                except Exception as e_resub:
                    print(f"Failed to re-subscribe after connection error: {e_resub}. Exiting subscriber task.")
                    break # Exit loop on re-subscription failure
            except Exception as e_listen:
                print(f"Unexpected error in Redis subscriber listen loop: {e_listen}")
                await asyncio.sleep(1)

    except asyncio.CancelledError:
        print("Redis subscriber task was cancelled.")
    except Exception as e: # Catch errors during initial pubsub setup
        print(f"Redis subscriber task ended due to an error: {e}")
    finally:
        if pubsub:
            try:
                await pubsub.punsubscribe("chat:*")
                await pubsub.close()
                print("Unsubscribed from Redis channels and closed pubsub.")
            except Exception as e_close:
                print(f"Error during pubsub cleanup: {e_close}")
        print("Redis message subscriber task finished.")
