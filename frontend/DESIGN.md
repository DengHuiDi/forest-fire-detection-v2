---
name: Sentient Guardian
colors:
  surface: '#0e1416'
  surface-dim: '#0e1416'
  surface-bright: '#343a3c'
  surface-container-lowest: '#090f11'
  surface-container-low: '#171d1e'
  surface-container: '#1b2122'
  surface-container-high: '#252b2d'
  surface-container-highest: '#303638'
  on-surface: '#dee3e6'
  on-surface-variant: '#bcc9cd'
  inverse-surface: '#dee3e6'
  inverse-on-surface: '#2b3133'
  outline: '#869397'
  outline-variant: '#3d494c'
  surface-tint: '#4cd7f6'
  primary: '#4cd7f6'
  on-primary: '#003640'
  primary-container: '#06b6d4'
  on-primary-container: '#00424f'
  inverse-primary: '#00687a'
  secondary: '#c0c1ff'
  on-secondary: '#1000a9'
  secondary-container: '#3131c0'
  on-secondary-container: '#b0b2ff'
  tertiary: '#ffb873'
  on-tertiary: '#4b2800'
  tertiary-container: '#e89337'
  on-tertiary-container: '#5b3200'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#acedff'
  primary-fixed-dim: '#4cd7f6'
  on-primary-fixed: '#001f26'
  on-primary-fixed-variant: '#004e5c'
  secondary-fixed: '#e1e0ff'
  secondary-fixed-dim: '#c0c1ff'
  on-secondary-fixed: '#07006c'
  on-secondary-fixed-variant: '#2f2ebe'
  tertiary-fixed: '#ffdcbf'
  tertiary-fixed-dim: '#ffb873'
  on-tertiary-fixed: '#2d1600'
  on-tertiary-fixed-variant: '#6a3b00'
  background: '#0e1416'
  on-background: '#dee3e6'
  surface-variant: '#303638'
typography:
  display-lg:
    fontFamily: Space Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: 0.02em
  body-base:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
    letterSpacing: 0em
  data-mono:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1'
    letterSpacing: 0.05em
  label-caps:
    fontFamily: Space Grotesk
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1'
    letterSpacing: 0.1em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  gutter: 16px
  margin: 24px
---

## Brand & Style

This design system is engineered for high-stakes environmental monitoring, where rapid data synthesis and immediate error-free responses are critical. The brand personality is clinical, vigilant, and technologically advanced. It evokes a sense of "Mission Control"—an authoritative and protective digital presence that remains calm under pressure.

The visual style employs a refined **Glassmorphism** aesthetic tailored for dark environments. By utilizing semi-transparent layers and luminous accents, the UI creates a sense of depth and hierarchy without overwhelming the user with heavy solid blocks. The interface feels like a heads-up display (HUD), prioritizing real-time data density and legibility through sharp contrasts and glowing status indicators.

## Colors

The palette is anchored in a deep, multi-tonal dark space. The background utilizes a radial or linear gradient from Deep Slate-950 to Indigo-950 to provide subtle depth and reduce ocular strain during long shifts.

- **Primary (Cyan-500):** Used for active states, navigational highlights, and structural borders. It represents the "System Online" state.
- **Danger (Red-500):** Reserved exclusively for critical fire alerts and immediate security breaches. It should be used with a subtle outer glow (0 0 10px) to simulate emergency lighting.
- **Warning (Amber-500):** Indicates potential risks, sensor malfunctions, or maintenance requirements.
- **Success (Emerald-500):** Communicates safe status and successful system checks.
- **Neutral/Base:** A 5% white overlay is used for glass panels to differentiate surfaces from the deep background.

## Typography

This design system utilizes a dual-font approach to balance futuristic technicality with high-speed readability. 

**Space Grotesk** is used for headlines, labels, and telemetry readouts to provide a technical, geometric "cyber" feel. **Inter** is used for body copy and system messaging to ensure maximum clarity and legibility of critical information. 

Data-dense areas should prioritize tabular figures and uppercase labels to facilitate rapid scanning of sensor logs. Use a slight letter-spacing increase for small-cap labels to prevent character bleed on backlit displays.

## Layout & Spacing

The system uses a **Fluid Grid** model with a base-4 increment system. The layout philosophy is "Data-Dense but Organized," utilizing a 12-column grid for dashboard views and a tight internal padding structure for information cards.

Gutters are kept tight (16px) to maximize screen real estate for map views and sensor arrays. Components should utilize `gap` properties rather than margins to maintain consistent rhythm in flex-based telemetry rows.

## Elevation & Depth

Depth is established through **Glassmorphism** and light-emission rather than traditional shadows. 

1.  **Base Layer:** The gradient background.
2.  **Surface Layer:** `bg-white/5` with `backdrop-blur-md`. This layer represents the standard containment for widgets and panels.
3.  **Active/Hover Layer:** `bg-white/10` with a `1px` border of `Cyan-500/30`. 
4.  **Floating/Alert Layer:** Components that require immediate attention use a high-intensity glow effect (`box-shadow: 0 0 15px -3px rgba(6, 182, 212, 0.5)`) to appear as if they are projecting light onto the surface below.

All borders on glass panels should be subtle (20% opacity) unless the element is in an active or "Alarm" state.

## Shapes

The shape language is "Soft-Technical." Elements use a consistent **Soft (0.25rem)** corner radius for primary containers to maintain a modern, engineered feel without the harshness of raw brutalism.

- **Standard Elements:** 4px (0.25rem) radius.
- **Large Panels/Cards:** 8px (0.5rem) radius.
- **Interactive Triggers:** Small buttons and inputs maintain the 4px radius to feel like physical tactile switches.
- **Indicators:** Circular indicators are reserved exclusively for status LEDs (Success/Danger/Warning).

## Components

- **Buttons:** Primary buttons use a solid Cyan-500 background with black text for maximum contrast. Secondary buttons are "Ghost" style with a Cyan-500/20 border and Cyan text.
- **Glass Panels:** Defined by `backdrop-blur-md`, a 1px border (`white/10`), and a slight top-down gradient to simulate light hitting the top edge of the glass.
- **Status Indicators:** Small "LED" circles. When "Active," they must feature an outer glow matching their semantic color (e.g., a Red-500 glow for fire alerts).
- **Inputs:** Dark backgrounds (`black/20`) with a bottom-only border or a very subtle 1px frame. Focus states must trigger a Cyan-500 glow.
- **Telemetry Cards:** Information-dense layouts using the `data-mono` typography. Labels are placed above values in `label-caps` style with 40% opacity.
- **Alert Banner:** Full-width, high-saturation Red-500 background with white bold text. This is the only component allowed to break the glassmorphism rules to ensure visual dominance.
- **Data Visualizations:** Line charts and graphs use high-vibrancy strokes with "Area" fills that utilize 10% opacity gradients of the stroke color.