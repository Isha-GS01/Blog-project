# act_innercircle/urls.py
"""
URL configuration for act_innercircle project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/

Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# ─────────────────────────────────────────────────────
# MAIN URL CONFIGURATION
# ─────────────────────────────────────────────────────
# This is the "main switchboard" — it routes incoming web requests
# to the correct app. The `include()` call means: "for anything
# starting with '', hand it off to knowledge_base/urls.py"

urlpatterns = [
    # Django Admin Panel
    path('admin/', admin.site.urls),
    
    # Knowledge Base App — All routes including auth, posts, API
    # Namespace 'knowledge_base' allows {% url 'knowledge_base:view_name' %}
    path('', include('knowledge_base.urls', namespace='knowledge_base')),
]

# ─────────────────────────────────────────────────────
# MEDIA FILES SERVING (Development Only)
# ─────────────────────────────────────────────────────
# WHY: During development, Django needs to serve uploaded images
# (like user avatars, post attachments). In production, a real
# web server (Nginx, Apache) does this. Never use DEBUG=True in production!

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ─────────────────────────────────────────────────────
# STATIC FILES SERVING (Optional, for completeness)
# ─────────────────────────────────────────────────────
# Uncomment if you want Django to also serve static files (CSS, JS)
# during development. In production, use a web server instead.

# if settings.DEBUG:
#     urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)