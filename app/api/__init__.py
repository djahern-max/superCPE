# app/api/__init__.py (Updated with modular routers)

from fastapi import APIRouter

# Create main API router
api_router = APIRouter()

print("🔍 Loading API routers...")

# Import and include auth router
try:
    from .auth import router as auth_router

    api_router.include_router(auth_router)
    print("✅ Auth router loaded successfully")
    print(f"   Auth routes: {[route.path for route in auth_router.routes]}")
except ImportError as e:
    print(f"❌ Could not load auth router: {e}")
except Exception as e:
    print(f"❌ Unexpected error loading auth router: {e}")

# Import and include the new modular certificate routers
try:
    from .certificate_upload import router as upload_router

    api_router.include_router(upload_router)
    print("✅ Certificate upload router loaded successfully")
    print(f"   Upload routes: {[route.path for route in upload_router.routes]}")
except ImportError as e:
    print(f"❌ Could not load certificate upload router: {e}")
except Exception as e:
    print(f"❌ Unexpected error loading certificate upload router: {e}")

try:
    from .certificate_data import router as data_router

    api_router.include_router(data_router)
    print("✅ Certificate data router loaded successfully")
    print(f"   Data routes: {[route.path for route in data_router.routes]}")
except ImportError as e:
    print(f"❌ Could not load certificate data router: {e}")
except Exception as e:
    print(f"❌ Unexpected error loading certificate data router: {e}")

try:
    from .ce_broker_exports import router as exports_router

    api_router.include_router(exports_router)
    print("✅ CE Broker exports router loaded successfully")
    print(f"   Export routes: {[route.path for route in exports_router.routes]}")
except ImportError as e:
    print(f"❌ Could not load CE Broker exports router: {e}")
except Exception as e:
    print(f"❌ Unexpected error loading CE Broker exports router: {e}")

try:
    from .file_management import router as files_router

    api_router.include_router(files_router)
    print("✅ File management router loaded successfully")
    print(f"   File routes: {[route.path for route in files_router.routes]}")
except ImportError as e:
    print(f"❌ Could not load file management router: {e}")
except Exception as e:
    print(f"❌ Unexpected error loading file management router: {e}")

print(f"🏁 Total API routes loaded: {len(api_router.routes)}")
print("📁 Modular certificate routers:")
print("   ├── certificate_upload.py")
print("   ├── certificate_data.py")
print("   ├── ce_broker_exports.py")
print("   └── file_management.py")
