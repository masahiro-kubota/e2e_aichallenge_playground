import { useEffect } from 'react';
import { DashboardLayout } from './components/DashboardLayout';
import { useSimulationStore } from './store/simulationStore';

function App() {
  const setData = useSimulationStore((state) => state.setData);

  useEffect(() => {
    // Check for injected data
    console.log('Checking for window.SIMULATION_DATA...');
    if (window.SIMULATION_DATA) {
      console.log('Found injected data:', window.SIMULATION_DATA);
      console.log('Data keys:', Object.keys(window.SIMULATION_DATA));
      if (window.SIMULATION_DATA.steps) {
        console.log('Number of steps:', window.SIMULATION_DATA.steps.length);
      }
      setData(window.SIMULATION_DATA);
    } else {
      // Fallback for development (fetch from local file or mock)
      console.warn("No injected data found. Trying to fetch 'simulation_log.json'...");
      fetch('/simulation_log.json')
        .then((res) => {
          console.log('Fetch response status:', res.status);
          return res.json();
        })
        .then((data) => {
          console.log('Fetched data successfully:', data);
          setData(data);
        })
        .catch((err) => console.error('Failed to load simulation data:', err));
    }
  }, [setData]);

  return <DashboardLayout />;
}

export default App;
