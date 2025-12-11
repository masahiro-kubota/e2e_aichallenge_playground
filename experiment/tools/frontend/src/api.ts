import type { ConfigResponse, MapResponse, Obstacle } from './types';

const API_BASE = '/api';

export async function loadConfig(yamlPath: string): Promise<ConfigResponse> {
    const response = await fetch(`${API_BASE}/config?yaml_path=${encodeURIComponent(yamlPath)}`);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to load config');
    }
    return response.json();
}

export async function loadMap(osmPath: string): Promise<MapResponse> {
    const response = await fetch(`${API_BASE}/map?osm_path=${encodeURIComponent(osmPath)}`);
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to load map');
    }
    return response.json();
}

export async function saveObstacles(yamlPath: string, obstacles: Obstacle[]): Promise<void> {
    const response = await fetch(`${API_BASE}/obstacles?yaml_path=${encodeURIComponent(yamlPath)}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ obstacles }),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save obstacles');
    }

    // Read the response to consume it
    await response.json();
}
