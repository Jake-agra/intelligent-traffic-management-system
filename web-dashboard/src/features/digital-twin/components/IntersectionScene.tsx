import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Component, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import * as THREE from "three";
import type { DigitalTwinViewModel, Direction, TwinSignal } from "../types";
import { DIRECTIONS } from "../types";

type CameraPreset = "overview" | "north" | "east";

const cameraPresets: Record<CameraPreset, [number, number, number]> = {
  overview: [7, 8, 7],
  north: [0, 5.5, 9],
  east: [9, 5.5, 0]
};

const lightPositions: Record<Direction, [number, number, number]> = {
  north: [-2.6, 0, -2.8],
  south: [2.6, 0, 2.8],
  east: [2.8, 0, -2.6],
  west: [-2.8, 0, 2.6]
};

const lightRotations: Record<Direction, number> = {
  north: 0,
  south: Math.PI,
  east: -Math.PI / 2,
  west: Math.PI / 2
};

const laneOffsets: Record<Direction, [number, number, number]> = {
  north: [-0.8, 0.16, 7.4],
  south: [0.8, 0.16, -7.4],
  east: [-7.4, 0.16, -0.8],
  west: [7.4, 0.16, 0.8]
};

const vehicleRotations: Record<Direction, number> = {
  north: 0,
  south: Math.PI,
  east: Math.PI / 2,
  west: -Math.PI / 2
};

const lampColors: Record<Exclude<TwinSignal, "unknown">, number> = {
  red: 0xde2d26,
  yellow: 0xffd166,
  green: 0x2ec76e
};

const vehicleColors = [0x1f5f8b, 0x8f3f71, 0x316b57, 0xb85c38, 0x46556a];

export function IntersectionScene({
  model,
  diagnostics
}: {
  model: DigitalTwinViewModel;
  diagnostics: SceneDiagnostics;
}) {
  const [preset, setPreset] = useState<CameraPreset>("overview");
  const [resetVersion, setResetVersion] = useState(0);
  const [sceneStatus, setSceneStatus] = useState<SceneStatus>(initialSceneStatus);
  const reportSceneStatus = useCallback((status: SceneStatus) => {
    setSceneStatus((current) => (sameSceneStatus(current, status) ? current : status));
  }, []);
  const resetCamera = () => {
    setPreset("overview");
    setResetVersion((version) => version + 1);
  };

  return (
    <section className="digital-twin-scene-panel" aria-label="3D intersection digital twin">
      <div className="scene-toolbar">
        <button className="button button--secondary" type="button" onClick={() => setPreset("overview")}>
          Overview
        </button>
        <button className="button button--secondary" type="button" onClick={() => setPreset("north")}>
          North
        </button>
        <button className="button button--secondary" type="button" onClick={() => setPreset("east")}>
          East
        </button>
        <button className="button" type="button" onClick={resetCamera}>
          Reset camera
        </button>
      </div>
      <div className="digital-twin-scene-viewport" data-testid="digital-twin-scene-viewport">
        <WebGLErrorBoundary fallback={<SceneFallback model={model} reason="The 3D scene crashed while rendering." />}>
          <ThreeIntersectionCanvas
            model={model}
            preset={preset}
            resetVersion={resetVersion}
            onStatus={reportSceneStatus}
          />
        </WebGLErrorBoundary>
        <DirectionLabels />
      </div>
      <SceneDiagnosticsPanel
        cameraPreset={preset}
        diagnostics={diagnostics}
        sceneStatus={sceneStatus}
      />
    </section>
  );
}

function ThreeIntersectionCanvas({
  model,
  preset,
  resetVersion,
  onStatus
}: {
  model: DigitalTwinViewModel;
  preset: CameraPreset;
  resetVersion: number;
  onStatus: (status: SceneStatus) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [failureReason, setFailureReason] = useState<string | null>(null);
  const testCanvas = useMemo(() => isTestMode(), []);
  const forcedFailure = isForcedCanvasFailure();

  useEffect(() => {
    if (forcedFailure) {
      const reason = "WebGL is unavailable: scene initialization was forced to fail.";
      setFailureReason(reason);
      onStatus({
        webglAvailable: false,
        canvasWidth: 0,
        canvasHeight: 0,
        sceneReady: false,
        failureReason: reason
      });
      return undefined;
    }

    if (testCanvas) {
      setFailureReason(null);
      onStatus({
        webglAvailable: false,
        canvasWidth: 0,
        canvasHeight: 0,
        sceneReady: true,
        failureReason: null
      });
      return undefined;
    }

    const canvas = canvasRef.current;
    if (!canvas) {
      return undefined;
    }

    setFailureReason(null);

    if (!hasWebGLSupport()) {
      const reason = "WebGL is unavailable in this browser.";
      setFailureReason(reason);
      onStatus({
        webglAvailable: false,
        canvasWidth: canvas.clientWidth,
        canvasHeight: canvas.clientHeight,
        sceneReady: false,
        failureReason: reason
      });
      return undefined;
    }

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: true,
        powerPreference: "default",
        preserveDrawingBuffer: true
      });
    } catch (error) {
      const reason = error instanceof Error ? error.message : "WebGL renderer could not start.";
      if (import.meta.env.DEV) {
        console.error("Digital twin WebGL initialization failed", error);
      }
      setFailureReason(`WebGL is unavailable: ${reason}`);
      onStatus({
        webglAvailable: false,
        canvasWidth: canvas.clientWidth,
        canvasHeight: canvas.clientHeight,
        sceneReady: false,
        failureReason: `WebGL is unavailable: ${reason}`
      });
      return undefined;
    }

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xdfe7ee);

    const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
    camera.position.set(...cameraPresets[preset]);
    camera.lookAt(0, 0, 0);

    const controls = new OrbitControls(camera, canvas);
    controls.enablePan = false;
    controls.minDistance = 5;
    controls.maxDistance = 16;
    controls.maxPolarAngle = Math.PI / 2.15;
    controls.target.set(0, 0, 0);
    controls.update();

    renderer.setClearColor(0xdfe7ee, 1);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));

    scene.add(new THREE.AmbientLight(0xffffff, 0.8));
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(6, 8, 4);
    scene.add(sun);
    scene.add(createRoadNetwork());

    DIRECTIONS.forEach((direction) => {
      scene.add(createTrafficLight(direction, model.directions[direction].signal));
    });

    const vehicles = createVehicles(model);
    vehicles.forEach((vehicle) => scene.add(vehicle.group));

    let reportedReady = false;
    const resize = () => {
      const width = Math.max(1, canvas.clientWidth);
      const height = Math.max(1, canvas.clientHeight);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      onStatus({
        webglAvailable: true,
        canvasWidth: width,
        canvasHeight: height,
        sceneReady: reportedReady,
        failureReason: null
      });
    };

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas);
    resize();

    let previousTime = performance.now();
    let frameId = 0;
    const animate = (time: number) => {
      const delta = Math.min(0.08, (time - previousTime) / 1000);
      previousTime = time;
      vehicles.forEach((vehicle) => advanceVehicle(vehicle, delta));
      controls.update();
      renderer.render(scene, camera);
      if (!reportedReady) {
        reportedReady = true;
        onStatus({
          webglAvailable: true,
          canvasWidth: canvas.clientWidth,
          canvasHeight: canvas.clientHeight,
          sceneReady: true,
          failureReason: null
        });
      }
      frameId = window.requestAnimationFrame(animate);
    };
    frameId = window.requestAnimationFrame(animate);

    return () => {
      window.cancelAnimationFrame(frameId);
      resizeObserver.disconnect();
      controls.dispose();
      disposeScene(scene);
      renderer.dispose();
    };
  }, [forcedFailure, model, onStatus, preset, resetVersion, testCanvas]);

  if (forcedFailure) {
    return (
      <SceneFallback
        model={model}
        reason="WebGL is unavailable: scene initialization was forced to fail."
      />
    );
  }

  if (failureReason) {
    return <SceneFallback model={model} reason={failureReason} />;
  }

  if (testCanvas) {
    return (
      <div
        aria-label="3D scene canvas"
        className="digital-twin-canvas"
        data-testid="digital-twin-scene-canvas"
      />
    );
  }

  return <canvas ref={canvasRef} aria-label="3D scene canvas" className="digital-twin-canvas" />;
}

function DirectionLabels() {
  return (
    <div className="scene-direction-labels" aria-label="Scene direction labels">
      {DIRECTIONS.map((direction) => (
        <span key={direction} className={`scene-direction-label scene-direction-label--${direction}`}>
          {direction.toUpperCase()}
        </span>
      ))}
    </div>
  );
}

function createRoadNetwork() {
  const group = new THREE.Group();
  group.add(box([18, 0.04, 18], [0, -0.03, 0], 0x7c8b78));
  group.add(box([3.8, 0.06, 18], [0, 0, 0], 0x252b31));
  const eastWest = box([3.8, 0.06, 18], [0, 0, 0], 0x252b31);
  eastWest.rotation.y = Math.PI / 2;
  group.add(eastWest);
  group.add(box([4.1, 0.05, 4.1], [0, 0.02, 0], 0x2f343a));

  [-6.5, -4.5, 4.5, 6.5].forEach((offset) => {
    group.add(box([0.08, 0.02, 1.1], [0, 0.06, offset], 0xf3f6f8));
    group.add(box([1.1, 0.02, 0.08], [offset, 0.06, 0], 0xf3f6f8));
  });
  [-2.35, 2.35].forEach((offset) => {
    group.add(box([3.6, 0.02, 0.08], [0, 0.07, offset], 0xf7d154));
    group.add(box([0.08, 0.02, 3.6], [offset, 0.07, 0], 0xf7d154));
  });

  return group;
}

function createTrafficLight(direction: Direction, signal: TwinSignal) {
  const group = new THREE.Group();
  group.position.set(...lightPositions[direction]);
  group.rotation.y = lightRotations[direction];

  const pole = new THREE.Mesh(
    new THREE.CylinderGeometry(0.04, 0.04, 1.3, 12),
    new THREE.MeshStandardMaterial({ color: 0x1d252d, roughness: 0.8 })
  );
  pole.position.set(0, 0.65, 0);
  group.add(pole);

  group.add(box([0.34, 0.82, 0.22], [0, 1.45, 0], 0x111820));
  group.add(lamp("red", signal === "red", 1.68));
  group.add(lamp("yellow", signal === "yellow", 1.45));
  group.add(lamp("green", signal === "green", 1.22));

  if (signal === "unknown") {
    const unknown = new THREE.Mesh(
      new THREE.SphereGeometry(0.07, 12, 12),
      new THREE.MeshStandardMaterial({ color: 0x8a94a3, emissive: 0x2f3742, emissiveIntensity: 0.25 })
    );
    unknown.position.set(0, 1.45, -0.12);
    group.add(unknown);
  }

  return group;
}

function lamp(color: Exclude<TwinSignal, "unknown">, active: boolean, y: number) {
  const material = new THREE.MeshStandardMaterial({
    color: active ? lampColors[color] : 0x2f3742,
    emissive: active ? lampColors[color] : 0x000000,
    emissiveIntensity: active ? 1.2 : 0,
    roughness: 0.35
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.075, 16, 16), material);
  mesh.position.set(0, y, -0.13);
  return mesh;
}

type SceneVehicle = {
  group: THREE.Group;
  direction: Direction;
  progress: number;
  signal: TwinSignal;
  speed: number;
};

function createVehicles(model: DigitalTwinViewModel): SceneVehicle[] {
  return DIRECTIONS.flatMap((direction) =>
    Array.from({ length: model.directions[direction].visualVehicleCount }, (_, index) => {
      const group = new THREE.Group();
      const progress = (index + 1) / (model.directions[direction].visualVehicleCount + 1);
      group.position.set(...positionFor(direction, progress));
      group.rotation.y = vehicleRotations[direction];
      group.add(box([0.42, 0.2, 0.78], [0, 0.02, 0], vehicleColors[index % vehicleColors.length]));
      group.add(box([0.32, 0.16, 0.36], [0, 0.15, -0.04], 0xd7e2ed));
      return {
        group,
        direction,
        progress,
        signal: model.directions[direction].signal,
        speed: 0.08 + (index % 3) * 0.012
      };
    })
  );
}

function advanceVehicle(vehicle: SceneVehicle, delta: number) {
  const beforeStopLine = vehicle.progress < 0.42;
  const mustStop =
    vehicle.signal === "red" ||
    vehicle.signal === "unknown" ||
    (vehicle.signal === "yellow" && beforeStopLine);
  if (!mustStop || !beforeStopLine) {
    vehicle.progress = (vehicle.progress + delta * vehicle.speed) % 1;
  }
  vehicle.group.position.set(...positionFor(vehicle.direction, vehicle.progress));
}

function positionFor(direction: Direction, progress: number): [number, number, number] {
  const [baseX, y, baseZ] = laneOffsets[direction];
  const span = 14.8;
  if (direction === "north") {
    return [baseX, y, baseZ - progress * span];
  }
  if (direction === "south") {
    return [baseX, y, baseZ + progress * span];
  }
  if (direction === "east") {
    return [baseX + progress * span, y, baseZ];
  }
  return [baseX - progress * span, y, baseZ];
}

function box(size: [number, number, number], position: [number, number, number], color: number) {
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(...size),
    new THREE.MeshStandardMaterial({ color, roughness: 0.75 })
  );
  mesh.position.set(...position);
  return mesh;
}

function disposeScene(scene: THREE.Scene) {
  scene.traverse((object) => {
    if (object instanceof THREE.Mesh) {
      object.geometry.dispose();
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach((material) => material.dispose());
    }
  });
}

function hasWebGLSupport() {
  const canvas = document.createElement("canvas");
  return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
}

function isTestMode() {
  return import.meta.env.MODE === "test";
}

function isForcedCanvasFailure() {
  return Boolean((globalThis as { __ITMS_FAIL_CANVAS?: boolean }).__ITMS_FAIL_CANVAS);
}

function SceneFallback({ model, reason }: { model: DigitalTwinViewModel; reason: string }) {
  return (
    <div className="state-panel state-panel--warning" role="status">
      {reason} Textual signal state remains available for {model.intersectionName}.
    </div>
  );
}

type SceneDiagnostics = {
  intersectionId: string;
  apiStatus: string;
  normalizedLaneCount: number;
  signalStateCount: number;
  vehicleVisualCount: number;
};

type SceneStatus = {
  webglAvailable: boolean;
  canvasWidth: number;
  canvasHeight: number;
  sceneReady: boolean;
  failureReason: string | null;
};

const initialSceneStatus: SceneStatus = {
  webglAvailable: false,
  canvasWidth: 0,
  canvasHeight: 0,
  sceneReady: false,
  failureReason: null
};

function SceneDiagnosticsPanel({
  cameraPreset,
  diagnostics,
  sceneStatus
}: {
  cameraPreset: CameraPreset;
  diagnostics: SceneDiagnostics;
  sceneStatus: SceneStatus;
}) {
  if (!showDevelopmentDiagnostics()) {
    return null;
  }

  return (
    <aside className="digital-twin-diagnostics" aria-label="Digital twin diagnostics">
      <strong>Scene diagnostics</strong>
      <dl>
        <div>
          <dt>WebGL available</dt>
          <dd>{sceneStatus.webglAvailable ? "yes" : "no"}</dd>
        </div>
        <div>
          <dt>Canvas</dt>
          <dd>
            {sceneStatus.canvasWidth} x {sceneStatus.canvasHeight}
          </dd>
        </div>
        <div>
          <dt>Intersection ID</dt>
          <dd>{diagnostics.intersectionId || "unknown"}</dd>
        </div>
        <div>
          <dt>API load status</dt>
          <dd>{diagnostics.apiStatus}</dd>
        </div>
        <div>
          <dt>Normalized lanes</dt>
          <dd>{diagnostics.normalizedLaneCount}</dd>
        </div>
        <div>
          <dt>Signal states</dt>
          <dd>{diagnostics.signalStateCount}</dd>
        </div>
        <div>
          <dt>Vehicle visuals</dt>
          <dd>{diagnostics.vehicleVisualCount}</dd>
        </div>
        <div>
          <dt>Camera preset</dt>
          <dd>{cameraPreset}</dd>
        </div>
        <div>
          <dt>Scene ready</dt>
          <dd>{sceneStatus.sceneReady ? "yes" : "no"}</dd>
        </div>
      </dl>
      {sceneStatus.failureReason ? <p>{sceneStatus.failureReason}</p> : null}
    </aside>
  );
}

function showDevelopmentDiagnostics() {
  return import.meta.env.DEV || import.meta.env.MODE === "test";
}

function sameSceneStatus(left: SceneStatus, right: SceneStatus) {
  return (
    left.webglAvailable === right.webglAvailable &&
    left.canvasWidth === right.canvasWidth &&
    left.canvasHeight === right.canvasHeight &&
    left.sceneReady === right.sceneReady &&
    left.failureReason === right.failureReason
  );
}

class WebGLErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

export type { Direction };
