# Intelligent Traffic Management System

A real-time AIoT traffic management platform aligned with the project documentation. The platform combines a professional web command dashboard, a synchronized mobile application, a FastAPI backend, PostgreSQL, MQTT/WebSockets, Raspberry Pi GPIO control, computer vision, and a 3D traffic simulation.

## Core documented modules

- Vehicle detection and counting
- Traffic density analysis: Low, Medium, High
- Adaptive traffic signal control
- Red-light violation detection
- Accident and abnormal-event detection
- Real-time dashboard and mobile monitoring
- Alerts and notifications
- Historical analytics and reporting
- Raspberry Pi edge processing
- GPIO traffic-light and buzzer control
- Simulated traffic-scenario testing

## Applications

- `backend/` — API, authentication, real-time events, database and MQTT integration
- `web-dashboard/` — responsive Traffic Operations Center
- `mobile-app/` — synchronized live operations and incident-response application
- `simulation/` — 3D digital-twin intersection and traffic scenarios
- `raspberry-pi/` — GPIO, camera, edge detection, MQTT and isolated hardware tests
- `docs/` — architecture, API contracts, hardware maps and documentation traceability

## Real-time synchronization

The web dashboard and mobile app consume the same backend API and WebSocket event stream. Neither client owns traffic state. PostgreSQL stores durable records, while the backend publishes authoritative live state for traffic readings, signal phases, incidents, violations, alerts and device health.

## Engineering principles

- Minimal, purposeful code
- Mobile and web parity for live operational information
- Backend as the single source of truth
- Isolated GPIO testing before hardware integration
- Responsive and accessible interfaces
- Lightweight dependencies and lazy-loaded heavy features
- Documented and testable modules

## Status

Repository foundation initialized. Implementation will proceed in tested phases, beginning with the backend and database foundation.