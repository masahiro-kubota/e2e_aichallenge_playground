export interface Point {
    x: number;
    y: number;
}

export interface MapLine {
    points: Point[];
}

export interface MapPolygon {
    points: Point[];
}

export interface ObstacleShape {
    type: 'rectangle' | 'circle';
    width?: number;
    length?: number;
    radius?: number;
}

export interface ObstaclePosition {
    x: number;
    y: number;
    yaw: number;
}

export interface Obstacle {
    type: 'static' | 'dynamic';
    shape: ObstacleShape;
    position: ObstaclePosition;
}

export interface ConfigResponse {
    obstacles: Obstacle[];
    map_path: string | null;
}

export interface MapResponse {
    map_lines: MapLine[];
    map_polygons: MapPolygon[];
}

export interface ViewTransform {
    offsetX: number;
    offsetY: number;
    scale: number;
}
