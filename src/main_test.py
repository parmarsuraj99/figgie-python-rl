from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fasthtml.common import *
from fasthtml.core import to_xml

# Create FastAPI app
fastapi_app = FastAPI()

# Helper function to render FastHTML components
def render_fasthtml(title, *components):
    # Use Titled to automatically create the full HTML structure
    full_page = Titled(title, *components)
    return "<!DOCTYPE html>\n" + to_xml(full_page)

# FastAPI route that uses FastHTML rendering
@fastapi_app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Check if the client wants JSON or HTML
    if request.headers.get("Accept") == "application/json":
        return JSONResponse({"message": "This is JSON content"})
    
    # Use FastHTML to create your HTML content
    title = "Welcome to FastHTML in FastAPI"
    content = [
        P("This is a hybrid FastAPI and FastHTML application.")
    ]
    
    # Render the FastHTML components
    html_content = render_fasthtml(title, *content)
    
    # Return as HTMLResponse
    return HTMLResponse(content=html_content)

# Run the FastAPI app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)