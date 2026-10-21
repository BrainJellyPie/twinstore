// @vitest-environment jsdom
import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { OrthographicCamera, Vector3 } from "three";
import { StoreCameraControls } from "../StoreCameraControls";
import { usePhotoMode } from "../photoModeStore";

const mocks = vi.hoisted(() => ({ get: vi.fn(), invalidate: vi.fn(), size: { width: 1000, height: 650 }, orbit: vi.fn() }));
vi.mock("@react-three/fiber", () => ({
  useThree: (select: (state: typeof mocks) => unknown) => select(mocks),
}));
vi.mock("@react-three/drei", async () => {
  const React = await import("react");
  const { Vector3 } = await import("three");
  return { OrbitControls: React.forwardRef((props: { camera: OrthographicCamera }, ref) => {
    React.useImperativeHandle(ref, () => ({ object: props.camera, target: new Vector3(), update: vi.fn(), enableDamping: true }), [props.camera]);
    mocks.orbit(props);
    return null;
  }) };
});

let camera: OrthographicCamera;
beforeEach(() => {
  vi.clearAllMocks();
  camera = new OrthographicCamera();
  mocks.get.mockReturnValue({ camera });
  mocks.size = { width: 1000, height: 650 };
  usePhotoMode.getState().stop();
});
afterEach(cleanup);

it("keeps a user view across mode and temporary-camera switches, then fits on request", () => {
  const view = render(<StoreCameraControls width={24} depth={18} disabled={false} fitRequest={0} />);
  const initialZoom = camera.zoom;
  expect(initialZoom).toBeGreaterThan(0);
  camera.zoom = 83;
  camera.position.set(21, 17, 26);
  view.rerender(<StoreCameraControls width={24} depth={18} disabled fitRequest={0} maxZoom={420} />);
  view.rerender(<StoreCameraControls width={24} depth={18} disabled={false} fitRequest={0} maxZoom={420} />);
  act(() => usePhotoMode.getState().start());
  act(() => usePhotoMode.getState().stop());
  expect(camera.zoom).toBe(83);
  expect(camera.position).toEqual(new Vector3(21, 17, 26));
  expect(mocks.invalidate).toHaveBeenCalledOnce();
  view.rerender(<StoreCameraControls width={24} depth={18} disabled={false} fitRequest={1} maxZoom={420} />);
  expect(camera.zoom).toBe(initialZoom);
  expect(camera.position).toEqual(new Vector3(17, 14.1, 22));
  expect(mocks.invalidate).toHaveBeenCalledTimes(2);
});

it("fits new dimensions and defers resizing while a temporary view is active", () => {
  const view = render(<StoreCameraControls width={8} depth={6} disabled={false} fitRequest={0} />);
  const compactZoom = camera.zoom;
  view.rerender(<StoreCameraControls width={40} depth={40} disabled={false} fitRequest={0} />);
  expect(camera.zoom).toBeLessThan(compactZoom);
  const largeZoom = camera.zoom;
  mocks.size = { width: 390, height: 600 };
  act(() => usePhotoMode.getState().start());
  expect(camera.zoom).toBe(largeZoom);
  act(() => usePhotoMode.getState().stop());
  expect(camera.zoom).toBeLessThan(largeZoom);
  expect(mocks.orbit.mock.lastCall![0].minZoom).toBeLessThan(camera.zoom);
  const mobileZoom = camera.zoom;
  mocks.size = { width: 600, height: 600 };
  view.rerender(<StoreCameraControls width={40} depth={40} disabled fitRequest={0} />);
  expect(camera.zoom).toBe(mobileZoom);
  view.rerender(<StoreCameraControls width={40} depth={40} disabled={false} fitRequest={0} />);
  expect(camera.zoom).toBeGreaterThan(mobileZoom);
});
