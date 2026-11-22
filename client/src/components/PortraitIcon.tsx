// client/src/components/PortraitIcon.tsx
// Stylized icon standing in for a portrait. No image generation is wired up yet,
// so this renders an honest curated icon rather than implying AI-generated art.
import React from 'react';
import { ShieldCheck, Ghost, Wand2, Sun, Footprints, User, LucideIcon } from 'lucide-react';

const PORTRAIT_ICON_BY_ID: Record<string, LucideIcon> = {
  sentinel: ShieldCheck,
  shadow: Ghost,
  arcane: Wand2,
  devout: Sun,
  wanderer: Footprints,
};

interface PortraitIconProps {
  portraitId?: string | null;
  className?: string;
}

export const PortraitIcon: React.FC<PortraitIconProps> = ({ portraitId, className = 'w-5 h-5' }) => {
  const Icon = (portraitId && PORTRAIT_ICON_BY_ID[portraitId]) || User;
  return <Icon className={className} aria-hidden="true" />;
};
