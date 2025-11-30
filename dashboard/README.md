# Dashboard

Interactive web-based dashboard for visualizing simulation results.

## Overview

This dashboard is a React + TypeScript application built with Vite. It provides:
- Real-time trajectory visualization
- Time-series plots for velocity, steering, acceleration, and yaw
- Interactive time slider for playback control

## Development

### Prerequisites

```bash
cd dashboard/frontend
npm install
```

### Development Server

Run the development server with hot module replacement (HMR):

```bash
npm run dev
```

This will start a local server at `http://localhost:5173` where you can preview changes in real-time.

### Building for Production

**IMPORTANT**: After making changes to the React code, you must rebuild the production bundle:

```bash
npm run build
```

This generates `dashboard/frontend/dist/index.html`, which is used by the Python `HTMLDashboardGenerator` to create simulation dashboards.

## Architecture

- **Frontend**: React + TypeScript + Vite + MUI (Material-UI)
- **State Management**: Zustand
- **Charts**: Recharts
- **Build**: Single-file HTML output (via `vite-plugin-singlefile`)

## Integration

The dashboard is integrated with the experiment runner:
1. `experiment-runner` generates simulation data
2. `HTMLDashboardGenerator` (Python) injects data into `dist/index.html`
3. The resulting HTML is uploaded to MLflow as an artifact

## Customization

### Theme

The dashboard uses MUI's default dark theme. To customize colors, edit `src/components/DashboardLayout.tsx`:

```typescript
const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    // Add custom colors here
  },
});
```

### Components

- `DashboardLayout.tsx`: Main layout and theme provider
- `TrajectoryView.tsx`: 2D trajectory visualization
- `TimeSeriesPlot.tsx`: Time-series charts
- `TimeSlider.tsx`: Playback control
