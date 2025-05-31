from enum import Enum

class UserRole(str, Enum): # System-level roles
    USER = "user"
    ADMIN = "admin" # Super Admin, can manage system-wide settings, all orgs etc.

class OrgRole(str, Enum): # Organization-level roles
    OWNER = "owner"         # Typically the creator, full control over org
    ADMIN = "admin"         # Can manage members, settings within THIS org
    MEMBER = "member"       # Basic member, can access shared resources
    SALES_REP = "sales_rep" # Specific role for sales functionalities
    SUPPORT_AGENT = "support_agent" # Specific role for support functionalities
