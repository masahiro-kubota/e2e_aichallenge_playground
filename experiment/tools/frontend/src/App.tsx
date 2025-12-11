import { useState, useRef, useEffect, useCallback } from 'react';
import type { Obstacle, MapPolygon, ViewTransform, Point } from './types';
import { loadConfig, loadMap, saveObstacles } from './api';
import {
  AppBar,
  Box,
  Button,
  TextField,
  Toolbar,
  Typography,
  Paper,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Divider,
  Alert,
  CssBaseline,
  ThemeProvider,
  createTheme,
} from '@mui/material';
import {
  Add as AddIcon,
  Circle as CircleIcon,
  Delete as DeleteIcon,
  Save as SaveIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';

const theme = createTheme();

function App() {
  const [yamlPath, setYamlPath] = useState('experiment/configs/modules/default_module.yaml');
  const [obstacles, setObstacles] = useState<Obstacle[]>([]);
  const [mapPolygons, setMapPolygons] = useState<MapPolygon[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [status, setStatus] = useState('準備完了');
  const [isDragging, setIsDragging] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const [dragStart, setDragStart] = useState<Point | null>(null);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [viewTransform, setViewTransform] = useState<ViewTransform>({
    offsetX: 0,
    offsetY: 0,
    scale: 1,
  });

  const handleLoad = async () => {
    try {
      setStatus('読み込み中...');
      const config = await loadConfig(yamlPath);
      console.log('Config loaded:', config);
      setObstacles(config.obstacles);

      if (config.map_path) {
        console.log('Loading map from:', config.map_path);
        const mapData = await loadMap(config.map_path);
        console.log('Map data loaded:', mapData);
        setMapPolygons(mapData.map_polygons);
        // fitMapToCanvas will be called by useEffect when mapPolygons changes
      } else {
        console.warn('No map_path in config');
      }

      setStatus(`読み込み完了: ${config.obstacles.length}個の障害物`);
    } catch (error) {
      setStatus(`エラー: ${error}`);
      console.error('Load error:', error);
    }
  };

  const fitMapToCanvas = (polygons: MapPolygon[]) => {
    const canvas = canvasRef.current;
    if (!canvas || polygons.length === 0) {
      console.log('fitMapToCanvas: canvas or polygons not available', { canvas: !!canvas, polygonsCount: polygons.length });
      return;
    }

    // Ensure canvas has size
    if (canvas.width === 0 || canvas.height === 0) {
      console.log('fitMapToCanvas: canvas has no size', { width: canvas.width, height: canvas.height });
      return;
    }

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

    polygons.forEach(polygon => {
      polygon.points.forEach(point => {
        minX = Math.min(minX, point.x);
        minY = Math.min(minY, point.y);
        maxX = Math.max(maxX, point.x);
        maxY = Math.max(maxY, point.y);
      });
    });

    const mapWidth = maxX - minX;
    const mapHeight = maxY - minY;
    const padding = 0.1; // 10% padding
    const scaleX = (canvas.width * (1 - padding * 2)) / mapWidth;
    const scaleY = (canvas.height * (1 - padding * 2)) / mapHeight;
    const scale = Math.min(scaleX, scaleY);

    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    const newTransform = {
      offsetX: canvas.width / 2 - centerX * scale,
      offsetY: canvas.height / 2 - centerY * scale,
      scale,
    };

    console.log('fitMapToCanvas:', {
      canvasSize: { width: canvas.width, height: canvas.height },
      mapBounds: { minX, minY, maxX, maxY, mapWidth, mapHeight },
      scale,
      newTransform
    });

    setViewTransform(newTransform);
  };

  const worldToScreen = useCallback((x: number, y: number): Point => {
    return {
      x: x * viewTransform.scale + viewTransform.offsetX,
      y: y * viewTransform.scale + viewTransform.offsetY,
    };
  }, [viewTransform]);

  const screenToWorld = useCallback((x: number, y: number): Point => {
    return {
      x: (x - viewTransform.offsetX) / viewTransform.scale,
      y: (y - viewTransform.offsetY) / viewTransform.scale,
    };
  }, [viewTransform]);

  const drawCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) {
      console.log('drawCanvas: canvas is null');
      return;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      console.log('drawCanvas: ctx is null');
      return;
    }

    console.log('drawCanvas: Drawing...', {
      canvasSize: { width: canvas.width, height: canvas.height },
      viewTransform,
      mapPolygonsCount: mapPolygons.length,
      obstaclesCount: obstacles.length
    });

    // Use MUI theme colors
    const bgColor = theme.palette.background.default;
    const primaryColor = theme.palette.primary.main;
    const primaryLight = theme.palette.primary.light;

    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw map polygons with MUI primary color
    ctx.fillStyle = `${primaryLight}33`; // 20% opacity
    ctx.strokeStyle = `${primaryColor}CC`; // 80% opacity
    ctx.lineWidth = 2;

    mapPolygons.forEach(polygon => {
      if (polygon.points.length === 0) return;

      ctx.beginPath();
      const first = worldToScreen(polygon.points[0].x, polygon.points[0].y);
      ctx.moveTo(first.x, first.y);

      polygon.points.slice(1).forEach(point => {
        const screen = worldToScreen(point.x, point.y);
        ctx.lineTo(screen.x, screen.y);
      });

      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    });

    // Draw obstacles
    obstacles.forEach((obstacle, index) => {
      const isSelected = index === selectedIndex;
      const pos = worldToScreen(obstacle.position.x, obstacle.position.y);

      ctx.save();
      ctx.translate(pos.x, pos.y);
      ctx.rotate(obstacle.position.yaw);

      if (obstacle.shape.type === 'rectangle') {
        const width = (obstacle.shape.width || 2) * viewTransform.scale;
        const length = (obstacle.shape.length || 4) * viewTransform.scale;

        const errorColor = theme.palette.error.main;
        const errorDark = theme.palette.error.dark;
        ctx.fillStyle = isSelected ? `${errorColor}B3` : `${errorColor}80`;
        ctx.strokeStyle = isSelected ? errorDark : errorColor;
        ctx.lineWidth = isSelected ? 3 : 2;

        ctx.fillRect(-length / 2, -width / 2, length, width);
        ctx.strokeRect(-length / 2, -width / 2, length, width);
      } else if (obstacle.shape.type === 'circle') {
        const radius = (obstacle.shape.radius || 1) * viewTransform.scale;

        const errorColor = theme.palette.error.main;
        const errorDark = theme.palette.error.dark;
        ctx.fillStyle = isSelected ? `${errorColor}B3` : `${errorColor}80`;
        ctx.strokeStyle = isSelected ? errorDark : errorColor;
        ctx.lineWidth = isSelected ? 3 : 2;

        ctx.beginPath();
        ctx.arc(0, 0, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }

      ctx.restore();

      if (isSelected) {
        ctx.fillStyle = primaryColor;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 5, 0, Math.PI * 2);
        ctx.fill();
      }
    });
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resizeCanvas = () => {
      const parent = canvas.parentElement;
      if (!parent) return;

      const rect = parent.getBoundingClientRect();
      canvas.width = rect.width;
      canvas.height = rect.height;
      drawCanvas();
    };

    // Initial resize
    resizeCanvas();

    // Watch for resize
    const resizeObserver = new ResizeObserver(resizeCanvas);
    resizeObserver.observe(canvas.parentElement!);

    return () => {
      resizeObserver.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fit map to canvas when mapPolygons are loaded
  useEffect(() => {
    if (mapPolygons.length > 0) {
      console.log('mapPolygons changed, count:', mapPolygons.length);
      // Use setTimeout to ensure canvas is sized
      setTimeout(() => {
        const canvas = canvasRef.current;
        if (canvas && canvas.width > 0 && canvas.height > 0) {
          console.log('Auto-fitting map to canvas');
          fitMapToCanvas(mapPolygons);
        } else {
          console.log('Canvas not ready for fitMapToCanvas', {
            canvas: !!canvas,
            width: canvas?.width,
            height: canvas?.height
          });
        }
      }, 200);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapPolygons]);

  // Redraw when viewTransform, obstacles, or mapPolygons change
  useEffect(() => {
    console.log('Redraw useEffect triggered, viewTransform:', viewTransform);
    // Force redraw using requestAnimationFrame
    requestAnimationFrame(() => {
      drawCanvas();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewTransform, obstacles, mapPolygons, selectedIndex]);

  // Handle wheel event with passive: false to prevent default scrolling
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      console.log('Canvas not found in wheel useEffect');
      return;
    }

    console.log('Setting up wheel event listener');

    const handleWheel = (e: WheelEvent) => {
      console.log('Wheel event fired!', e.deltaY);
      e.preventDefault();

      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const scaleFactor = e.deltaY > 0 ? 0.9 : 1.1;

      setViewTransform(prev => {
        const newScale = Math.max(0.1, Math.min(10, prev.scale * scaleFactor));

        // Calculate mouse position in world coordinates BEFORE zoom
        const worldX = (mouseX - prev.offsetX) / prev.scale;
        const worldY = (mouseY - prev.offsetY) / prev.scale;

        // Calculate new offset so that the world point under the mouse stays in the same screen position
        const newOffsetX = mouseX - worldX * newScale;
        const newOffsetY = mouseY - worldY * newScale;

        console.log('Zoom:', {
          prevScale: prev.scale,
          newScale,
          mouseScreen: { x: mouseX, y: mouseY },
          worldPos: { x: worldX, y: worldY },
          prevOffset: { x: prev.offsetX, y: prev.offsetY },
          newOffset: { x: newOffsetX, y: newOffsetY }
        });

        return {
          scale: newScale,
          offsetX: newOffsetX,
          offsetY: newOffsetY,
        };
      });
    };

    canvas.addEventListener('wheel', handleWheel, { passive: false });
    console.log('Wheel event listener added');

    return () => {
      canvas.removeEventListener('wheel', handleWheel);
      console.log('Wheel event listener removed');
    };
  }, []); // Empty dependency array - handleWheel uses setViewTransform with function form

  const handleCanvasMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const worldPos = screenToWorld(x, y);

    if (e.button === 1 || e.ctrlKey) {
      setIsPanning(true);
      setDragStart({ x, y });
      return;
    }

    let clickedIndex = -1;
    for (let i = obstacles.length - 1; i >= 0; i--) {
      const obstacle = obstacles[i];
      const dx = worldPos.x - obstacle.position.x;
      const dy = worldPos.y - obstacle.position.y;

      if (obstacle.shape.type === 'rectangle') {
        const width = obstacle.shape.width || 2;
        const length = obstacle.shape.length || 4;
        const cos = Math.cos(-obstacle.position.yaw);
        const sin = Math.sin(-obstacle.position.yaw);
        const localX = dx * cos - dy * sin;
        const locally = dx * sin + dy * cos;

        if (Math.abs(localX) <= length / 2 && Math.abs(locally) <= width / 2) {
          clickedIndex = i;
          break;
        }
      } else if (obstacle.shape.type === 'circle') {
        const radius = obstacle.shape.radius || 1;
        if (Math.sqrt(dx * dx + dy * dy) <= radius) {
          clickedIndex = i;
          break;
        }
      }
    }

    if (clickedIndex >= 0) {
      setSelectedIndex(clickedIndex);
      setIsDragging(true);
      setDragStart(worldPos);
    } else {
      setSelectedIndex(null);
    }
  };

  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !dragStart) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (isPanning) {
      const dx = x - dragStart.x;
      const dy = y - dragStart.y;
      setViewTransform(prev => ({
        ...prev,
        offsetX: prev.offsetX + dx,
        offsetY: prev.offsetY + dy,
      }));
      setDragStart({ x, y });
    } else if (isDragging && selectedIndex !== null) {
      const worldPos = screenToWorld(x, y);
      const dx = worldPos.x - dragStart.x;
      const dy = worldPos.y - dragStart.y;

      setObstacles(prev => {
        const updated = [...prev];
        updated[selectedIndex] = {
          ...updated[selectedIndex],
          position: {
            ...updated[selectedIndex].position,
            x: updated[selectedIndex].position.x + dx,
            y: updated[selectedIndex].position.y + dy,
          },
        };
        return updated;
      });

      setDragStart(worldPos);
    }
  };

  const handleCanvasMouseUp = () => {
    setIsDragging(false);
    setIsPanning(false);
    setDragStart(null);
  };

  const addObstacle = (shapeType: 'rectangle' | 'circle') => {
    const newObstacle: Obstacle = {
      type: 'static',
      shape: shapeType === 'rectangle'
        ? { type: 'rectangle', width: 2, length: 4 }
        : { type: 'circle', radius: 1 },
      position: { x: 0, y: 0, yaw: 0 },
    };

    setObstacles(prev => [...prev, newObstacle]);
    setSelectedIndex(obstacles.length);
    setStatus(`${shapeType === 'rectangle' ? '矩形' : '円形'}を追加しました`);
  };

  const deleteSelected = () => {
    if (selectedIndex === null) return;

    setObstacles(prev => prev.filter((_, i) => i !== selectedIndex));
    setSelectedIndex(null);
    setStatus('障害物を削除しました');
  };

  const handleSave = async () => {
    try {
      setStatus('保存中...');
      await saveObstacles(yamlPath, obstacles);
      setStatus('保存完了');
    } catch (error) {
      setStatus(`保存エラー: ${error}`);
      console.error(error);
    }
  };

  const updateSelectedObstacle = (updates: Partial<Obstacle>) => {
    if (selectedIndex === null) return;

    setObstacles(prev => {
      const updated = [...prev];
      updated[selectedIndex] = { ...updated[selectedIndex], ...updates };
      return updated;
    });
  };

  const selectedObstacle = selectedIndex !== null ? obstacles[selectedIndex] : null;

  // Auto-load on mount
  useEffect(() => {
    handleLoad();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
        <AppBar position="static">
          <Toolbar>
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              🚧 障害物エディター
            </Typography>
          </Toolbar>
        </AppBar>

        <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', p: 2, overflow: 'hidden' }}>
          <Paper sx={{ p: 2, mb: 2 }}>
            <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
              <TextField
                label="YAMLファイルパス"
                value={yamlPath}
                onChange={(e) => setYamlPath(e.target.value)}
                fullWidth
                size="small"
              />
              <Button
                variant="contained"
                startIcon={<RefreshIcon />}
                onClick={handleLoad}
                sx={{ minWidth: 120 }}
              >
                読み込み
              </Button>
            </Stack>

            <Stack direction="row" spacing={1} flexWrap="wrap">
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={() => addObstacle('rectangle')}
              >
                矩形を追加
              </Button>
              <Button
                variant="outlined"
                startIcon={<CircleIcon />}
                onClick={() => addObstacle('circle')}
              >
                円形を追加
              </Button>
              <Button
                variant="outlined"
                color="error"
                startIcon={<DeleteIcon />}
                onClick={deleteSelected}
                disabled={selectedIndex === null}
              >
                削除
              </Button>
              <Button
                variant="contained"
                color="success"
                startIcon={<SaveIcon />}
                onClick={handleSave}
                disabled={obstacles.length === 0}
              >
                保存
              </Button>
            </Stack>
          </Paper>

          <Box sx={{ flexGrow: 1, display: 'grid', gridTemplateColumns: '1fr 350px', gap: 2, minHeight: 0 }}>
            <Paper sx={{ position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <Box sx={{ flexGrow: 1, position: 'relative' }}>
                <canvas
                  ref={canvasRef}
                  onMouseDown={handleCanvasMouseDown}
                  onMouseMove={handleCanvasMouseMove}
                  onMouseUp={handleCanvasMouseUp}
                  onMouseLeave={handleCanvasMouseUp}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    cursor: 'crosshair'
                  }}
                />
              </Box>
              <Alert severity="info" sx={{ borderRadius: 0 }}>
                {status}
              </Alert>
            </Paper>

            <Paper sx={{ p: 2, overflow: 'auto' }}>
              <Typography variant="h6" gutterBottom>
                プロパティ
              </Typography>
              <Divider sx={{ mb: 2 }} />

              {selectedObstacle ? (
                <Stack spacing={2}>
                  <FormControl fullWidth size="small">
                    <InputLabel>タイプ</InputLabel>
                    <Select
                      value={selectedObstacle.type}
                      label="タイプ"
                      onChange={(e) => updateSelectedObstacle({ type: e.target.value as 'static' | 'dynamic' })}
                    >
                      <MenuItem value="static">静的</MenuItem>
                      <MenuItem value="dynamic">動的</MenuItem>
                    </Select>
                  </FormControl>

                  <FormControl fullWidth size="small">
                    <InputLabel>形状</InputLabel>
                    <Select
                      value={selectedObstacle.shape.type}
                      label="形状"
                      onChange={(e) => {
                        const shapeType = e.target.value as 'rectangle' | 'circle';
                        updateSelectedObstacle({
                          shape: shapeType === 'rectangle'
                            ? { type: 'rectangle', width: 2, length: 4 }
                            : { type: 'circle', radius: 1 }
                        });
                      }}
                    >
                      <MenuItem value="rectangle">矩形</MenuItem>
                      <MenuItem value="circle">円形</MenuItem>
                    </Select>
                  </FormControl>

                  {selectedObstacle.shape.type === 'rectangle' ? (
                    <>
                      <TextField
                        label="幅 (width)"
                        type="number"
                        size="small"
                        value={selectedObstacle.shape.width || 2}
                        onChange={(e) => updateSelectedObstacle({
                          shape: { ...selectedObstacle.shape, width: parseFloat(e.target.value) }
                        })}
                        inputProps={{ step: 0.1 }}
                      />
                      <TextField
                        label="長さ (length)"
                        type="number"
                        size="small"
                        value={selectedObstacle.shape.length || 4}
                        onChange={(e) => updateSelectedObstacle({
                          shape: { ...selectedObstacle.shape, length: parseFloat(e.target.value) }
                        })}
                        inputProps={{ step: 0.1 }}
                      />
                    </>
                  ) : (
                    <TextField
                      label="半径 (radius)"
                      type="number"
                      size="small"
                      value={selectedObstacle.shape.radius || 1}
                      onChange={(e) => updateSelectedObstacle({
                        shape: { ...selectedObstacle.shape, radius: parseFloat(e.target.value) }
                      })}
                      inputProps={{ step: 0.1 }}
                    />
                  )}

                  <Divider />

                  <TextField
                    label="X座標"
                    type="number"
                    size="small"
                    value={selectedObstacle.position.x.toFixed(3)}
                    onChange={(e) => updateSelectedObstacle({
                      position: { ...selectedObstacle.position, x: parseFloat(e.target.value) }
                    })}
                    inputProps={{ step: 0.1 }}
                  />

                  <TextField
                    label="Y座標"
                    type="number"
                    size="small"
                    value={selectedObstacle.position.y.toFixed(3)}
                    onChange={(e) => updateSelectedObstacle({
                      position: { ...selectedObstacle.position, y: parseFloat(e.target.value) }
                    })}
                    inputProps={{ step: 0.1 }}
                  />

                  <TextField
                    label="回転角 (yaw, rad)"
                    type="number"
                    size="small"
                    value={selectedObstacle.position.yaw.toFixed(3)}
                    onChange={(e) => updateSelectedObstacle({
                      position: { ...selectedObstacle.position, yaw: parseFloat(e.target.value) }
                    })}
                    inputProps={{ step: 0.1 }}
                  />
                </Stack>
              ) : (
                <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ py: 4 }}>
                  障害物を選択してください
                </Typography>
              )}
            </Paper>
          </Box>
        </Box>
      </Box>
    </ThemeProvider>
  );
}

export default App;
