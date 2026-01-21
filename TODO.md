# TODO - pyupload

## v0.1 Preliminary Planning & Setup
- [x] Document application overview
- [x] Document legacy database schema
- [x] Document initial feature parity requirements
- [x] Research and select Python web/API framework
- [x] Research and select Front-end strategy (HTMX)
- [x] Establish development environment with Docker Compose
- [x] Implement database models mapping to legacy schema
- [x] Implement core business logic layer (app/lib/)
- [x] Implement JWT authentication with access and refresh tokens
- [x] Implement automatic token refresh middleware
- [ ] Implement basic file upload and storage logic
- [ ] Implement basic file viewing and delivery logic

## Frontend Scaffolding
- [x] Integrate Tailwind CSS build system with automatic watching
- [x] Integrate Alpine.js for client-side interactivity
- [x] Convert base template from Bootstrap to Tailwind
- [x] Implement navbar with container-constrained content
- [x] Implement responsive navbar (mobile/sm/md breakpoints)
- [ ] Refine mobile breakpoint styling (needs content first)
- [ ] Add full navigation menu access at small breakpoint (currently only Upload visible)
- [ ] Implement dynamic Browse dropdown text based on active route
- [ ] Add conditional rendering for authenticated vs. anonymous users

## Future Authentication Enhancements
- [ ] Migrate to pwdlib recommended password hashing algorithms
- [ ] Implement configurable password complexity requirements (uppercase/lowercase/numbers/special chars)
- [ ] Implement two-factor authentication (2FA) support
