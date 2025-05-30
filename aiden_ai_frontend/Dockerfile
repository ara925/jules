# Use an official Nginx runtime as a parent image
FROM nginx:alpine

# Remove default Nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy static assets from the current folder to Nginx public HTML folder
COPY . /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Default command to start Nginx
CMD ["nginx", "-g", "daemon off;"]
