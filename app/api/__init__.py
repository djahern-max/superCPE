# app/api/__init__.py - FIXED VERSION

from fastapi import APIRouter

# Create main API router
api_router = APIRouter()

print("🔍 Loading API routers...")

# Import and include auth router - FIXED: Conditional loading
try:
    from .auth import router as auth_router

    api_router.include_router(auth_router)
    print("✅ Auth router loaded successfully")
    print(f"   Auth routes: {[route.path for route in auth_router.routes]}")
except ImportError as e:
    print(f"⚠️  Auth router not available: {e}")
    print("   → This is OK for testing without auth")
except Exception as e:
    print(f"❌ Unexpected error loading auth router: {e}")

# Import and include certificate upload router - FIXED: Better error handling
try:
    from .certificate_upload import router as upload_router

    api_router.include_router(upload_router)
    print("✅ Certificate upload router loaded successfully")
    print(f"   Upload routes: {[route.path for route in upload_router.routes]}")
except ImportError as e:
    print(f"❌ Could not load certificate upload router: {e}")
    import traceback

    traceback.print_exc()
except Exception as e:
    print(f"❌ Unexpected error loading certificate upload router: {e}")
    import traceback

    traceback.print_exc()

# Import and include certificate data router
try:
    from .certificate_data import router as data_router

    api_router.include_router(data_router)
    print("✅ Certificate data router loaded successfully")
    print(f"   Data routes: {[route.path for route in data_router.routes]}")
except ImportError as e:
    print(f"⚠️  Certificate data router not available: {e}")
except Exception as e:
    print(f"❌ Unexpected error loading certificate data router: {e}")

# Import and include CE Broker exports router
try:
    from .ce_broker_exports import router as exports_router

    api_router.include_router(exports_router)
    print("✅ CE Broker exports router loaded successfully")
    print(f"   Export routes: {[route.path for route in exports_router.routes]}")
except ImportError as e:
    print(f"⚠️  CE Broker exports router not available: {e}")
except Exception as e:
    print(f"❌ Unexpected error loading CE Broker exports router: {e}")

# Import and include file management router
try:
    from .file_management import router as files_router

    api_router.include_router(files_router)
    print("✅ File management router loaded successfully")
    print(f"   File routes: {[route.path for route in files_router.routes]}")
except ImportError as e:
    print(f"⚠️  File management router not available: {e}")
except Exception as e:
    print(f"❌ Unexpected error loading file management router: {e}")

print(f"🏁 Total API routes loaded: {len(api_router.routes)}")
print("📁 Available routers:")
print("   ├── certificate_upload.py (priority)")
print("   ├── certificate_data.py")
print("   ├── ce_broker_exports.py")
print("   ├── file_management.py")
print("   └── auth.py (if available)")

# Verify critical routes are loaded
upload_routes = [route.path for route in api_router.routes if "/upload" in route.path]
if upload_routes:
    print(f"✅ Upload functionality ready: {upload_routes}")
else:
    print("❌ No upload routes found - check certificate_upload.py")
