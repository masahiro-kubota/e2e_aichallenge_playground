import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'

// Set root element to full height
const rootElement = document.getElementById('root')!;
rootElement.style.width = '100%';
rootElement.style.height = '100vh';
rootElement.style.margin = '0';
rootElement.style.padding = '0';

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
