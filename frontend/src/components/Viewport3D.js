import React from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Box, Text, Grid } from '@react-three/drei';

export function Viewport3D({ geometry }) {
  const {
    length = 6,
    width = 4,
    height = 2.5,
    wall_thickness = 0.2,
    roof_thickness = 0.2,
    floor_thickness = 0.2,
    window_area = 2,
    window_orientation = 180,
  } = geometry;

  const windowWidth = Math.sqrt(window_area);
  const windowHeight = window_area / windowWidth;
  const wallH = height - wall_thickness * 2;
  const wallL = length - wall_thickness * 2;

  return (
    <div className="card mb-8" style={{ height: '400px' }}>
      <h3 className="text-lg font-semibold text-gray-900 mb-4">3D Shelter Preview</h3>
      <Canvas camera={{ position: [12, 8, 12], fov: 45 }}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[10, 15, 10]} intensity={1} castShadow />
        <directionalLight position={[-5, 10, -5]} intensity={0.5} />

        <OrbitControls
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          minDistance={5}
          maxDistance={30}
        />

        <Grid
          infiniteGrid
          cellSize={1}
          sectionSize={5}
          fadeDistance={30}
          fadeStrength={1}
          position={[0, -0.01, 0]}
        />

        <group position={[0, height / 2, 0]}>
          {/* Outer shell (transparent) */}
          <Box args={[length, height, width]} castShadow receiveShadow>
            <meshStandardMaterial
              color={0x9e9e9e}
              roughness={0.8}
              metalness={0.1}
              transparent
              opacity={0.15}
            />
          </Box>

          {/* Front wall */}
          <Box
            args={[wallL, wallH, wall_thickness]}
            position={[0, 0, width / 2 - wall_thickness / 2]}
            castShadow
            receiveShadow
          >
            <meshStandardMaterial color={0x9e9e9e} roughness={0.7} metalness={0.1} />
          </Box>

          {/* Back wall */}
          <Box
            args={[wallL, wallH, wall_thickness]}
            position={[0, 0, -width / 2 + wall_thickness / 2]}
            castShadow
            receiveShadow
          >
            <meshStandardMaterial color={0x9e9e9e} roughness={0.7} metalness={0.1} />
          </Box>

          {/* Right wall */}
          <Box
            args={[wall_thickness, wallH, width - wall_thickness * 2]}
            position={[length / 2 - wall_thickness / 2, 0, 0]}
            castShadow
            receiveShadow
          >
            <meshStandardMaterial color={0x9e9e9e} roughness={0.7} metalness={0.1} />
          </Box>

          {/* Left wall */}
          <Box
            args={[wall_thickness, wallH, width - wall_thickness * 2]}
            position={[-length / 2 + wall_thickness / 2, 0, 0]}
            castShadow
            receiveShadow
          >
            <meshStandardMaterial color={0x9e9e9e} roughness={0.7} metalness={0.1} />
          </Box>

          {/* Roof */}
          <Box
            args={[length, roof_thickness, width]}
            position={[0, height / 2 + roof_thickness / 2, 0]}
            castShadow
            receiveShadow
          >
            <meshStandardMaterial color={0x8b7355} roughness={0.6} metalness={0.1} />
          </Box>

          {/* Floor */}
          <Box
            args={[length, floor_thickness, width]}
            position={[0, -height / 2 - floor_thickness / 2, 0]}
            castShadow
            receiveShadow
          >
            <meshStandardMaterial color={0x7f8c8d} roughness={0.7} metalness={0.1} />
          </Box>

          {/* Window */}
          {window_area > 0 && (
            <Box
              args={[0.05, windowHeight, windowWidth]}
              position={[
                length / 2 - wall_thickness / 2 + 0.025,
                0,
                (window_orientation - 180) * (width / 360)
              ]}
              castShadow
              receiveShadow
            >
              <meshStandardMaterial
                color={0x87ceeb}
                roughness={0.1}
                metalness={0.9}
                transparent
                opacity={0.6}
              />
            </Box>
          )}
        </group>

        <Text
          position={[0, height + 1.2, 0]}
          fontSize={0.5}
          color="gray"
          anchorX="center"
        >
          {length}m x {width}m x {height}m
        </Text>
      </Canvas>
    </div>
  );
}