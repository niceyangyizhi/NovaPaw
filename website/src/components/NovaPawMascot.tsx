/**
 * NovaPaw mascot (same as logo symbol). Used in Hero and Nav.
 */
import { CatPawIcon } from "./CatPawIcon";

interface NovaPawMascotProps {
  size?: number;
  className?: string;
}

export function NovaPawMascot({
  size = 80,
  className = "",
}: NovaPawMascotProps) {
  return <CatPawIcon size={size} className={className} />;
}
