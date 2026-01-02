# Comparison: NiceGUI vs. FastAPI + HTMX

This comparison demonstrates how a "Rotate Image" feature would be implemented in both frameworks. This feature requires a backend action (image rotation) and a frontend update (refreshing the image and showing a notice).

## 1. NiceGUI Implementation

NiceGUI uses a persistent WebSocket connection. Event handlers are Python functions that directly manipulate UI components.

```python
from nicegui import ui

class ImagePage:
    def __init__(self, image_id):
        self.image_id = image_id
        self.angle = 0
        
        with ui.column().classes('w-full items-center'):
            # The image component is bound to state
            self.img_display = ui.image(f'/files/{image_id}.jpg').classes('w-64')
            
            with ui.row():
                ui.button('Rotate 90°', on_click=self.handle_rotate)

    async def handle_rotate(self):
        # 1. Backend Logic (Simulated)
        self.angle = (self.angle + 90) % 360
        # image_processing.rotate(self.image_id, 90)
        
        # 2. UI Update (Direct manipulation via WebSocket)
        # We append a timestamp to force a browser refresh of the cached image
        self.img_display.set_source(f'/files/{self.image_id}.jpg?t={time.time()}')
        ui.notify(f'Image rotated to {self.angle}°')
```

### Observations (NiceGUI):
- **Pros**: Extremely fast to write; no "request/response" cycle to manage manually.
- **Cons**: Requires a **stay-alive WebSocket**. If the connection drops, the button stops working. Harder to separate "Backend API" from "Frontend UI" as they share the same memory space.

---

## 2. FastAPI + HTMX Implementation

FastAPI handles standard HTTP requests. HTMX provides the interactivity by requesting small chunks of HTML.

### Backend (app/main.py)
```python
@app.post("/image/{image_id}/rotate")
async def rotate_image(image_id: int):
    # 1. Backend Logic
    # image_processing.rotate(image_id, 90)
    
    # 2. Return ONLY the HTML fragment that needs to change
    # HTMX will swap this content into the existing page
    timestamp = int(time.time())
    return HTMLResponse(content=f"""
        <div id="image-container" class="fade-in">
            <img src="/files/{image_id}.jpg?t={timestamp}" class="w-64">
            <div class="alert alert-success">Image rotated successfully!</div>
        </div>
    """)
```

### Frontend (app/templates/view.html)
```html
<!-- The container that HTMX will update -->
<div id="image-container">
    <img src="/files/{{ image_id }}.jpg" class="w-64">
</div>

<!-- The button tells HTMX: 
     1. Post to this URL
     2. Take the response and replace #image-container -->
<button class="btn btn-primary"
        hx-post="/image/{{ image_id }}/rotate"
        hx-target="#image-container"
        hx-swap="outerHTML">
    Rotate 90°
</button>
```

### Observations (FastAPI + HTMX):
- **Pros**: **Stateless HTTP**. Works just like a standard website. The "Backend" is a clean REST-like endpoint that can be tested independently. No persistent WebSocket required.
- **Cons**: Requires managing HTML templates.

---

## Why FastAPI + HTMX wins for `pyupload`:

1.  **Reliability**: Unlike NiceGUI, if a user has a spotty connection, the page remains functional.
2.  **Scalability**: Standard HTTP requests are easier to load-balance and cache than persistent WebSockets.
3.  **Separation**: You can easily build a "Headless" version of the API later (e.g., for a mobile app) because the logic is already broken down into standard endpoints.
4.  **Legacy Feel**: It feels more like the "Old Web" (PHP style) but with "New Web" responsiveness.
