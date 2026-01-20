"use client";

import { useEffect, useRef } from "react";
import createGlobe from "cobe";

export interface Marker {
  lat: number;
  lng: number;
  size: number;
}

interface GlobeProps {
  markers: Marker[];
  className?: string;
}

export default function Globe({ markers, className }: GlobeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointerInteracting = useRef<number | null>(null);
  const pointerMovement = useRef(0);
  const phiRef = useRef(0);
  const widthRef = useRef(0);

  useEffect(() => {
    if (!canvasRef.current) return;

    const onResize = () => {
      if (canvasRef.current) {
        widthRef.current = canvasRef.current.offsetWidth;
      }
    };
    window.addEventListener("resize", onResize);
    onResize();

    const globe = createGlobe(canvasRef.current, {
      devicePixelRatio: 2,
      width: widthRef.current * 2,
      height: widthRef.current * 2,
      phi: 0,
      theta: 0.25,
      dark: 1,
      diffuse: 1.2,
      mapSamples: 20000,
      mapBrightness: 4,
      baseColor: [0.12, 0.12, 0.14],
      markerColor: [0.9, 0.15, 0.15],
      glowColor: [0.08, 0.03, 0.06],
      markers: markers.map((m) => ({
        location: [m.lat, m.lng] as [number, number],
        size: m.size,
      })),
      onRender: (state) => {
        if (!pointerInteracting.current) {
          phiRef.current += 0.002;
        }
        state.phi = phiRef.current + pointerMovement.current / 200;
        state.width = widthRef.current * 2;
        state.height = widthRef.current * 2;
      },
    });

    return () => {
      globe.destroy();
      window.removeEventListener("resize", onResize);
    };
  }, [markers]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{ width: "100%", aspectRatio: "1", cursor: "grab" }}
      onPointerDown={(e) => {
        pointerInteracting.current = e.clientX - pointerMovement.current;
        if (canvasRef.current) canvasRef.current.style.cursor = "grabbing";
      }}
      onPointerUp={() => {
        pointerInteracting.current = null;
        if (canvasRef.current) canvasRef.current.style.cursor = "grab";
      }}
      onPointerOut={() => {
        pointerInteracting.current = null;
        if (canvasRef.current) canvasRef.current.style.cursor = "grab";
      }}
      onPointerMove={(e) => {
        if (pointerInteracting.current !== null) {
          pointerMovement.current = e.clientX - pointerInteracting.current;
        }
      }}
    />
  );
}
