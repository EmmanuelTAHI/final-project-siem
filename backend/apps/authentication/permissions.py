"""
Permissions spécifiques à l'authentification.
"""
from rest_framework.permissions import AllowAny

# Les endpoints d'authentification sont publics (login, OAuth initiate/callback)
# Les permissions spécifiques aux rôles SOC sont dans utils/permissions.py
