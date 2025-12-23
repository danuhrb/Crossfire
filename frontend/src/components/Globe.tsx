"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import createGlobe from "cobe";

interface AttackArc {
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  color: [number, number, number];
}

interface GlobeProps {
  attacks: AttackArc[];
  width?: number;
  height?: number;
  targetLat?: number;
  targetLng?: number;
}

export default function Globe({
  attacks,
  width = 800,
  height = 800,
  targetLat = 39.8283,
  targetLng = -98.5795,
}: GlobeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointerInteracting = useRef<number | null>(null);
  const pointerInteractionMovement = useRef(0);
  const [rotation, setRotation] = useState(0);

  const arcsData = useCallback(() => {
    return attacks.map((a) => ({
      startLat: a.startLat,
      startLng: a.startLng,
      endLat: a.endLat,
      endLng: a.endLng,
      arcAlt: 0.3,
      color: a.color,
    }));
  }, [attacks]);

  useEffect(() => {
    let phi = 0;
    let currentWidth = width;

    if (!canvasRef.current) return;

    const globe = createGlobe(canvasRef.current, {
      devicePixelRatio: 2,
      width: currentWidth * 2,
      height: height * 2,
      phi: 0,
      theta: 0.3,
      dark: 1,
      diffuse: 1.2,
      mapSamples: 16000,
      mapBrightness: 6,
      baseColor: [0.1, 0.1, 0.1],
      markerColor: [1, 0.2, 0.2],
      glowColor: [0.05, 0.05, 0.15],
      markers: attacks.map((a) => ({
        location: [a.startLat, a.startLng],
        size: 0.06,
      })),
      onRender: (state) => {
        if (!pointerInteracting.current) {
          phi += 0.003;
        }
        state.phi = phi + rotation;
        state.width = currentWidth * 2;
        state.height = height * 2;
      },
    });

    return () => {
      globe.destroy();
    };
  }, [attacks, width, height, rotation]);

  return (
    <div className="relative flex items-center justify-center">
      <canvas
        ref={canvasRef}
        style={{
          width: `${width}px`,
          height: `${height}px`,
          cursor: "grab",
          maxWidth: "100%",
          aspectRatio: "1",
        }}
        onPointerDown={(e) => {
          pointerInteracting.current =
            e.clientX - pointerInteractionMovement.current;
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
            const delta = e.clientX - pointerInteracting.current;
            pointerInteractionMovement.current = delta;
            setRotation(delta / 200);
          }
        }}
      />
      <div className="absolute bottom-4 left-4 text-xs text-zinc-500 font-mono">
        {attacks.length} active sources
      </div>
    </div>
  );
}
