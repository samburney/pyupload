# Code Style Guide — pyupload

This guide documents the coding conventions used in *pyupload*.  It is intended for both human contributors and LLM agents.  It covers Python source files under `app/` and Jinja2 templates under `app/ui/templates/`.  The `tests/` directory is excluded — tests are LLM-maintained and may not conform to these conventions.

This guide follows PEP 8 except where noted.  The primary deviation is line length: this guide uses a maximum of **88 characters** (the `black`/`ruff` default) rather than PEP 8's 79.


## Python

### Imports

Every distinct import style and namespace is its own group, separated from the next by a single blank line.  The full order is:

1. **stdlib** `import X`
2. **stdlib** `from X import Y`
3. **third-party** `import X`
4. **third-party** `from X import Y`
5. **`app.lib`**
6. **`app.models`**
7. **`app.ui`**

Within each group, lines are sorted alphabetically by module name.  Imported names on a `from X import Y` line are also sorted alphabetically.  Groups that have no members are omitted (no double blank lines).

```python
import asyncio
import json

from datetime import datetime, timezone

import bcrypt

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from tortoise.expressions import Q

from app.lib.auth import get_current_user_from_request
from app.lib.config import get_app_config

from app.models.uploads import Upload, UploadSerializer
from app.models.users import User

from app.ui.common.breadcrumbs import Breadcrumbs
from app.ui.common.gallery import render_gallery_index
```

**Bare `import X`** is correct when the module is used as a namespace prefix in code (`json.dumps`, `re.match`, `asyncio.gather`).  Use `from X import Y` when importing specific names to avoid repeated prefix noise.

**Module aliases** (`import app.lib.auth as lib_auth`) are acceptable to resolve name conflicts, but should be rare.

A `from X import Y` line that exceeds the line length limit must be expanded into parenthesised multi-line form with one name per line and a trailing comma.  Names within a multi-line import are sorted alphabetically:

```python
from app.ui.common.gallery import (
    GalleryPaginationDefaultParams,
    render_gallery_index,
    render_multiselect_sidebar,
)
```

Single-name imports that fit within the line length limit remain on one line:

```python
from app.lib.auth import get_current_user_from_request
```

`TYPE_CHECKING` guards are used for imports that are only needed for type annotations, to avoid circular imports:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.images import Image
```


### Type Annotations

All function signatures include parameter and return type annotations.

**Use `X | None` — never `Optional[X]`:**

```python
async def get_current_user(request: Request) -> User | None:
```

**Use built-in generic types — never `List`, `Dict`, `Tuple` from `typing`:**

```python
def page_data(self) -> dict[str, Any]: ...
selected_ids: list[int]
```

**FastAPI dependencies use `Annotated[T, Depends(...)]`** — this is the modern form and must be used consistently.  The old-style `param: T = Depends(...)` is not used:

```python
# Correct
pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
current_user: Annotated[User, Depends(get_current_authenticated_user)],

# Incorrect — do not use
pagination: GalleryPaginationDefaultParams = Depends(),
```


### Async

Use `async def` for all route handlers and any function that performs I/O (database queries, file access, external calls).

Plain `def` is correct for pure computation, property accessors, and configuration helpers that perform no I/O.


### Route Handlers

Routers are module-level globals:

```python
router = APIRouter(prefix='/gallery', tags=['gallery'])
breadcrumb_handler = Breadcrumbs(router=router, route_title="Browse")
```

Route handlers always specify `response_class`:

```python
@router.get("", response_class=Response)
async def gallery_index_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render the main gallery view."""
```

Route handler names follow the pattern `{noun}_{verb}_{http_method}`, e.g. `gallery_index_get`, `create_upload_post`, `delete_selected_uploads_post`.


### TemplateResponse

Template responses follow a fixed structure:

1. Assign to a local variable named `response`
2. Use multiline format with keyword arguments throughout
3. A blank line before `return response`

```python
response = templates.TemplateResponse(
    request=request,
    name="gallery/index.html.j2",
    context={
        "current_user": current_user,
        "breadcrumbs": breadcrumbs.get_all(),
        "uploads": uploads,
        "pagination": pagination,
    },
)

return response
```

`current_user` must always be present in the context, even when `None`.  Templates must never use `{% if current_user is defined %}` to guard against a missing key — a missing `current_user` should raise an error, not silently degrade.

When a context variable is optional (i.e. legitimately absent from some callers), use Jinja2's `default` filter or `is not defined` guard in the template, and document why the variable is optional.


### Error Handling

Four mechanisms exist, each with a distinct purpose:

**`HTTPException`** is a FastAPI primitive that returns a machine-readable HTTP error response.  Use it only in JSON API routes (`app/api/`), never in UI routes.

```python
# Correct — JSON API route
raise HTTPException(status_code=404, detail="Upload not found")
```

**`error_template_response`**, **`info_template_response`**, and (forthcoming) **`warning_template_response`** render user-facing full-page HTML responses.  Use them in UI routes whenever a request cannot be fulfilled and a full error or status page is appropriate.  They resolve `current_user` internally from `request` — it does not need to be passed by the caller.

```python
return await error_template_response(
    request, ["Tag not found."], status_code=404, title="Not Found"
)

return await info_template_response(
    request, ["Your request is being processed."], status_code=202
)
```

HTMX partial responses (components) are not full pages and do not use these helpers.  They return `templates.TemplateResponse` directly with an appropriate `status_code`.

**`flash_message`** adds an inline notification displayed alongside an otherwise normally-rendered page.  It is also shown on pages rendered by the template response helpers above.  Use it for informational messages, warnings, and non-fatal errors within a successful page render.

```python
flash_message(request, "Upload deleted successfully.")
flash_message(request, "You are not registered.", "warning")
```


### ORM Patterns

Use `get_or_none` for single-object lookups that may not exist:

```python
upload = await Upload.get_or_none(id=id)
if upload is None:
    ...
```

Eager-load related models using `prefetch_related` with the module-level constant:

```python
UPLOAD_PREFETCH_MODELS = ("user", "images", "tags", "collections")

uploads = Upload.paginate(...).prefetch_related(*UPLOAD_PREFETCH_MODELS)
```

Filter queries are built with `Q` objects and composed with `&` and `|`:

```python
pagination_query = default_readable_query_filter(current_user)
if context_filter is not None:
    pagination_query &= context_filter
```


### Naming

| Entity | Convention | Example |
|---|---|------|
| Files | `snake_case` | `gallery.py`, `error_handling.py` |
| Classes | `PascalCase` | `Upload`, `GalleryPaginationDefaultParams` |
| Functions / methods | `snake_case` | `render_gallery_index`, `get_upload_or_404` |
| Route handlers | `{noun}_{verb}_{method}` | `gallery_index_get`, `create_upload_post` |
| Variables | `snake_case` | `current_user`, `pagination_query` |
| Constants | `UPPER_SNAKE_CASE` | `UPLOAD_PREFETCH_MODELS`, `EXTENSION_PATTERN` |
| URL paths | `kebab-case` | `/gallery/update-selected`, `/tags/view/{name}` |
| Template context keys | `snake_case` strings | `"current_user"`, `"breadcrumbs"` |


### String Quotes

Double quotes are the default for all strings.  Single quotes are used when the string content contains double quotes, to avoid escaping:

```python
"Login successful!"          # default
"Upload not found"           # default
'He said "hello"'            # contains double quotes — use single outer
f'<a href="{url}">link</a>'  # f-string containing double quotes — use single outer
```

This applies to f-strings, regular strings, and multiline strings alike.  The rule is: prefer double quotes; switch to single only to avoid a backslash escape.


### String Formatting

f-strings are the standard for all string interpolation:

```python
url = f"{config.app_base_url}/get/{self.id}/{self.cleanname}{self.dot_ext}"
flash_message(request, f"Deleted {count} upload{'s' if count != 1 else ''}.")
```

String concatenation with `+` is not used for interpolation.


### Line Length and Wrapping

Lines must not exceed **88 characters**.  Parentheses are preferred for wrapping — backslash continuation is acceptable for ORM method chains:

```python
# Parentheses — preferred
response = templates.TemplateResponse(
    request=request,
    name="...",
)

# Backslash — acceptable for ORM method chains
upload_models = Upload.filter(id__in=ids) \
    .prefetch_related(*UPLOAD_PREFETCH_MODELS) \
    .order_by("-created_at")
```

Multi-line constructs always use trailing commas.


### Blank Lines

- Two blank lines between top-level definitions (PEP 8)
- Single blank line between logical sections within a function
- Single blank line before `return response` when the response was built above it
- Single blank line between import groups


### Docstrings and Comments

Route handlers have a single-line docstring:

```python
async def gallery_index_get(...) -> Response:
    """Render the main gallery view."""
```

Complex utility functions may use multi-line docstrings when parameters or return values need explanation.

Inline comments explain *why*, not *what*.  A comment above a block of code is preferred over an end-of-line comment:

```python
# Bail out early — only HTMX requests are valid here
if not request.headers.get('hx-request', False):
    raise HTTPException(status_code=400, detail='Not a valid HTMX request')
```

Section separator comments (`# Login page`, `# Register form submission`) are used in route files to group related handlers.


---

## Jinja2 Templates

### File Location and Naming

Templates live under `app/ui/templates/`.  Full-page templates sit in a directory named after their router (e.g. `gallery/index.html.j2`).  Reusable partials live under `components/`.

File names use `kebab-case` with the `.html.j2` extension.


### Inheritance

Page templates extend the base layout:

```jinja2
{%- extends "components/layout/base.html.j2" %}

{% block content %}
...
{% endblock %}
```


### Includes and Imports

Include paths are always **relative to the template root** (no leading `/`):

```jinja2
{# Correct #}
{% include "components/gallery/grid.html.j2" %}

{# Incorrect #}
{% include "/components/gallery/grid.html.j2" %}
```

Macros are imported with `with context` when they need access to template variables:

```jinja2
{%- from "components/gallery/multiselect-chrome.html.j2" import render_multiselect_chrome with context %}
```


### Context Variable Guards

`{% if X is defined %}` must not be used to guard against a missing `current_user` — this should be an error.

For variables that are genuinely optional, use `is not defined` guards or Jinja2's `default` filter, and document why the variable is optional:

```jinja2
{# sidebar_target is optional — defaults to "upload-sidebar" if not supplied by the caller #}
{% if sidebar_target is not defined %}{% set sidebar_target = "upload-sidebar" %}{% endif %}

{# or equivalently #}
{{ empty_content_title | default("There's nothing here!") }}
```

For `current_user`, always use truthiness checks only:

```jinja2
{% if current_user and current_user.is_authenticated %}
```


### Whitespace Control

Use `{%-` to suppress preceding whitespace at the top of a file (typically the `extends` tag) to avoid unintentional blank lines in output.  Do not apply it globally — use it only where whitespace in the rendered output would be a problem.


---

## HTML

### Doctype and Document Structure

Pages are served as HTML5 documents:

```html
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        ...
    </head>
    <body>
        ...
    </body>
</html>
```

Void elements (`<meta>`, `<link>`, `<input>`, `<br>`, `<img>`) are never self-closed — no trailing slash.


### Indentation

**4 spaces** per level throughout all HTML templates.


### Semantic Elements

Semantic elements are preferred over generic `<div>` and `<span>` wherever appropriate: `<nav>`, `<main>`, `<aside>`, `<article>`, `<footer>`, `<section>`, `<dl>`, `<dt>`, `<dd>`.


### Attribute Quotes

All HTML attribute values use **double quotes**.


### IDs

`id` values use `kebab-case`.


### Attribute Ordering

When an element carries multiple attributes they follow this order:

| Group | Attributes |
|---|---|
| a. Unique identifiers | `id`, `name` |
| b. Element-specific | `type`, `href`, `src`, `action` |
| c. Styling | `style`, then `class` |
| d. Standard HTML | `for`, `value`, `required`, `disabled`, `placeholder`, `target`, `rel`, `alt`, `title`, etc. |
| e. `hx-boost` | Standalone — always in this position; never mixed into standard or HTMX groups |
| f. Alpine.js | `x-data` → `x-init` → `x-ref` → `x-model` → `x-show`/`x-cloak`/`x-transition` → `:attr` bindings → `@event` handlers |
| g. HTMX | see sub-order below |
| h. Accessibility | `role`, `aria-*`, `tabindex` |

**HTMX attribute sub-order (g):**

| Sub-group | Attributes |
|---|---|
| Event | `hx-trigger` |
| Request | `hx-get` / `hx-post` / `hx-put` / `hx-delete` / `hx-patch` |
| Target | `hx-target`, `hx-target-4*`, `hx-sync` |
| Vars | `hx-vals`, `hx-include`, `hx-params` |
| Selection | `hx-select`, `hx-select-oob` |
| Swap | `hx-swap` |
| Action | `hx-indicator` |

`hx-trigger` is listed first even when omitted — its absence signals that the element uses the default trigger behaviour for its type.

When attributes must wrap across lines, each goes on its own line indented one level from the opening tag. The closing `>` sits at the end of the last attribute line:

```html
<!-- Alpine example -->
<div id="multiselect-chrome"
    class="flex flex-col"
    x-data="handleSelectedUploads"
    @clear-selection="clearSelection()">

<!-- HTMX example -->
<div id="sidebar-request-trigger"
    class="hidden"
    hx-trigger="update-sidebar from:body delay:200ms"
    hx-post="/gallery/selected"
    hx-target="#gallery-sidebar"
    hx-sync="this:replace"
    hx-include="[name='selected_ids']"
    hx-select="#gallery-sidebar"
    hx-swap="outerHTML swap:150ms settle:150ms"
    hx-indicator="#sidebar-content">
```


### SVG Icons

All icons are embedded as SVG sprites and referenced with `<use href="#...">`.  This avoids extra network requests while serving only the icons actually used.

**New icons** must come from [Material Symbols Outlined](https://fonts.google.com/icons).  Their sprite symbols are auto-generated by `scripts/build-icons-sprite.mjs` from the `@material-symbols/svg-400` npm package — run `npm run build:icons` after adding a new reference.  IDs follow the pattern `material-symbols-outlined-{icon-name}` where the icon name matches the Material Symbols name with hyphens instead of underscores:

```html
<svg class="size-4" aria-hidden="true" viewBox="0 -960 960 960">
    <use href="#material-symbols-outlined-delete"></use>
</svg>
```

**Legacy icons** with the `#icon-*` prefix remain in `components/common/icons-sprite.html.j2` and are maintained by hand.  These should be migrated to Material Symbols equivalents over time; no new `#icon-*` symbols should be added.

Decorative icons carry `aria-hidden="true"`. When an icon conveys meaning, `aria-label` belongs on the interactive parent element (the `<button>` or `<a>`), not the `<svg>` itself.


### Accessibility

- `type` is specified on all `<button>` elements
- Icon-only interactive elements carry `aria-label`
- Decorative SVGs carry `aria-hidden="true"`
- Dialog elements carry `role="dialog"`, `aria-modal="true"`, and `aria-labelledby` referencing the dialog title


### Comments

HTML comments (`<!-- -->`) label major layout sections within a template:

```html
<!-- Desktop menu - center navigation -->
<div class="hidden sm:flex items-center space-x-6">
```

Jinja2 comments (`{# #}`) annotate template-level concerns — context variable behaviour, macro usage, non-obvious logic — and are not rendered in output.


---

## CSS

This project uses **Tailwind CSS v4**.  The source file is `input.css`; the compiled output is `app/static/css/tailwind.css`.


### File Structure

`input.css` follows this top-to-bottom order:

1. `@import "tailwindcss"` and `@plugin` declarations
2. `@source` directive
3. `@theme {}` — custom design tokens (breakpoints, etc.)
4. `@layer base {}` — element-level defaults (`h1`, `h2`, form controls)
5. `@layer components {}` — selector-based and ID-specific styles
6. `@utility name {}` blocks — reusable composable utilities
7. `@keyframes {}` — animations


### Custom Utilities

Custom utility classes are defined with `@utility`:

```css
@utility button {
    @apply bg-blue-500 border border-blue-500 text-white py-2 px-4 rounded-md;

    &:disabled {
        @apply bg-gray-400 cursor-not-allowed;
    }
}
```

Names use **`kebab-case`**.  Variants follow these suffix conventions:

| Suffix type | Examples |
|---|---|
| Colour / semantic | `-alert`, `-warning`, `-ok`, `-neutral`, `-ghost`, `-dark` |
| Size | `-xs`, `-sm`, `-md` |
| Modifier | `-outline`, `-disabled` |

CSS nesting with `&` is used for state and hover variants within a block.  Section headers use `/* Comment */`.


### `@layer components` vs `@utility`

Use **`@layer components`** for styles that cannot be expressed as a composable utility — specific element IDs, HTMX state selectors, animation state selectors:

```css
@layer components {
    .htmx-request .htmx-indicator { display: flex !important; }
    #gallery-sidebar.sidebar-not-loaded { animation: fadeIn 150ms ease-in-out; }
}
```

Use **`@utility`** for any class applied directly to elements in templates.


### Indentation

4-space indentation throughout `input.css`.


---

## JavaScript

App JavaScript lives under `app/static/js/app/`.  Files are grouped by feature (`gallery/`, `uploads/`) or role (`lib/` for shared utilities).  Vendor libraries under `app/static/js/vendor/` are not modified.


### File Header

Every app JS file opens with a `/* ... */` block comment describing its purpose:

```js
/* HTMX helper functions for pyupload frontend */
```


### Module Patterns

**Alpine components, stores, and magic helpers** are registered inside a single `alpine:init` listener per file:

```js
document.addEventListener('alpine:init', () => {
    Alpine.data('tagInput', () => ({
        menu: false,
        newTag: '',

        update() { ... }
    }));
});
```

**HTMX event listeners** are attached at module level:

```js
document.addEventListener('htmx:beforeRequest', function(event) {
    ...
});
```

**Standalone utility functions** are defined at module level, outside any event listener.


### Naming

| Entity | Convention | Example |
|---|---|---|
| Functions | `camelCase` | `calculateDisplaySize`, `sweetConfirm` |
| Variables / constants | `camelCase` | `breakpoints`, `currentLoadedWidth` |
| Alpine data names | `camelCase` | `handleSelectedUploads`, `tagInput` |
| Alpine store names | `camelCase` | `uploadWidget` |


### Syntax

**Variable declarations**: `const` for values that do not change; `let` for values that may.  `var` is not used.

**Semicolons**: required on all statements.  ASI is not relied upon.

**String quotes**: single quotes by default; double quotes only when the string content contains a single quote.  Template literals for interpolation:

```js
const event = 'alpine:init';
const selector = 'input[name="selected_upload_ids"]';  // contains single quote — use double
const key = `selected-${id}`;                          // interpolation — use template literal
```

**Equality**: `===` and `!==` always.  `==` and `!=` are not used.

**Arrow functions** for callbacks, array methods, and short handlers:

```js
const ids = checkboxes.map(cb => cb.value);
setTimeout(() => { this.pulse = false; }, 200);
```


### Indentation

4-space indentation throughout.


### Comments

`/* ... */` for file-level descriptions.  `//` for inline explanations.  Comments explain *why*, not *what* — the same principle as Python.
