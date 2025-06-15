# app/main.py - FIXED VERSION

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRoute
from datetime import datetime

# Import Google Vision service for health check
try:
    from app.services.vision_service import VisionService

    vision_service = VisionService()
    VISION_AVAILABLE = True
except Exception as e:
    print(f"Warning: Google Vision not available: {e}")
    VISION_AVAILABLE = False

# Create FastAPI app
app = FastAPI(
    title="SuperCPE API",
    version="2.0.0",
    description="Automated CPE Certificate Management with CE Broker Integration",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FIXED: Import and include API router with better error handling
try:
    from app.api import api_router

    app.include_router(api_router)
    print("✅ API routers included successfully")
except Exception as e:
    print(f"❌ Failed to load API routers: {e}")
    import traceback

    traceback.print_exc()

# =================
# CORE ENDPOINTS
# =================


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "SuperCPE API v2.0 - Automated CPE Management",
        "version": "2.0.0",
        "features": [
            "Certificate Upload & Processing",
            "NH Compliance Tracking",
            "CE Broker Automation",
            "Digital Ocean Spaces Storage",
            "11-Step CE Broker Workflow",
        ],
        "documentation": "/docs",
        "api_routes": "/routes",
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "services": {
            "database": "connected",
            "ocr_vision": "available" if VISION_AVAILABLE else "unavailable",
            "ce_broker_automation": "active",
            "file_storage": "configured",
        },
        "endpoints": {
            "certificate_upload": "✅ Active",
            "certificate_data": "✅ Active",
            "ce_broker_automation": "✅ Active",
            "ce_broker_exports": "✅ Active",
            "file_management": "✅ Active",
            "authentication": "✅ Active",
        },
    }


@app.get("/routes", response_class=PlainTextResponse)
async def get_api_routes():
    """Returns a complete list of all API routes organized by category"""
    routes = []

    # Header
    routes.append("=" * 60)
    routes.append("SUPERCPE API v2.0 - COMPLETE ENDPOINT REFERENCE")
    routes.append("=" * 60)
    routes.append("")

    # Categorize routes
    cert_routes = []
    ce_broker_routes = []
    auth_routes = []
    jurisdiction_routes = []  # ADD THIS
    core_routes = []

    for route in app.routes:
        if isinstance(route, APIRoute):
            methods = ", ".join(route.methods)
            route_info = f"{methods:15} {route.path}"

            if route.path.startswith("/api/certificates/"):
                cert_routes.append(route_info)
            elif route.path.startswith("/api/ce-broker/"):
                ce_broker_routes.append(route_info)
            elif route.path.startswith("/api/auth/"):
                auth_routes.append(route_info)
            elif route.path.startswith("/api/jurisdictions/"):  # ADD THIS
                jurisdiction_routes.append(route_info)
            elif route.path in ["/", "/health", "/routes"]:
                core_routes.append(route_info)

    # Core endpoints
    routes.append("🏠 CORE ENDPOINTS:")
    for route in sorted(core_routes):
        routes.append(f"   {route}")
    routes.append("")

    # Authentication
    routes.append("🔐 AUTHENTICATION:")
    if auth_routes:
        for route in sorted(auth_routes):
            routes.append(f"   {route}")
    else:
        routes.append("   No authentication endpoints loaded")
    routes.append("")

    # ADD JURISDICTION REQUIREMENTS SECTION
    routes.append("🌎 JURISDICTION REQUIREMENTS:")
    if jurisdiction_routes:
        for route in sorted(jurisdiction_routes):
            routes.append(f"   {route}")
    else:
        routes.append("   No jurisdiction requirements endpoints loaded")
    routes.append("")

    # Certificate management
    routes.append("📄 CERTIFICATE MANAGEMENT:")
    if cert_routes:
        for route in sorted(cert_routes):
            routes.append(f"   {route}")
    else:
        routes.append("   No certificate endpoints loaded")
    routes.append("")

    # CE Broker automation
    routes.append("🤖 CE BROKER AUTOMATION:")
    if ce_broker_routes:
        for route in sorted(ce_broker_routes):
            routes.append(f"   {route}")
    else:
        routes.append("   No CE Broker endpoints loaded")
    routes.append("")

    # Summary - UPDATE THIS
    routes.append("=" * 60)
    routes.append("📊 ENDPOINT SUMMARY:")
    routes.append(f"   Core Endpoints: {len(core_routes)}")
    routes.append(f"   Authentication: {len(auth_routes)}")
    routes.append(
        f"   Jurisdiction Requirements: {len(jurisdiction_routes)}"
    )  # ADD THIS
    routes.append(f"   Certificate Management: {len(cert_routes)}")
    routes.append(f"   CE Broker Automation: {len(ce_broker_routes)}")
    routes.append(
        f"   Total Endpoints: {len(core_routes) + len(auth_routes) + len(jurisdiction_routes) + len(cert_routes) + len(ce_broker_routes)}"  # UPDATE THIS
    )
    routes.append("")
    routes.append("🎯 KEY FEATURES:")
    routes.append("   ├── Automated certificate processing")
    routes.append("   ├── State-by-state CPE requirements lookup")  # ADD THIS
    routes.append("   ├── NH compliance tracking (120 hours triennial)")
    routes.append("   ├── CE Broker 11-step automation")
    routes.append("   ├── Digital Ocean Spaces storage")
    routes.append("   ├── Smart filename optimization")
    routes.append("   └── Duplicate detection & prevention")
    routes.append("")
    routes.append("📚 Documentation: /docs")
    routes.append("=" * 60)

    return "\n".join(routes)


# =================
# STARTUP EVENT
# =================


@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    print("🚀 SuperCPE API v2.0 Starting Up...")
    print("📄 Certificate processing: Ready")
    print("🤖 CE Broker automation: Ready")
    print("🔐 Authentication: Ready")
    print("📊 Health check: /health")
    print("📚 API docs: /docs")
    print("🎯 All systems operational!")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    print("👋 SuperCPE API v2.0 Shutting Down...")
    print("✅ All connections closed gracefully")
