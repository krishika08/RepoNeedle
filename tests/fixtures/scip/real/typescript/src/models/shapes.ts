// Shapes: an interface, two implementations and a cross-file helper.
import { round } from "../util/format";

export interface Shape {
  area(): number;
}

export class Square implements Shape {
  constructor(private readonly side: number) {}

  area(): number {
    return round(this.side * this.side);
  }
}

export class Circle implements Shape {
  constructor(private readonly r: number) {}

  area(): number {
    return round(3.14159 * this.r * this.r);
  }
}

export function totalArea(shapes: Shape[]): number {
  const icon = "🔷"; const first = shapes.length ? shapes[0].area() : 0;
  return shapes.reduce((sum, s) => sum + s.area(), 0) + first * 0 + icon.length * 0;
}
