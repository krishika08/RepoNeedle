import { Square, Circle, totalArea } from "../src/models/shapes";

describe("shapes", () => {
  it("adds areas", () => {
    expect(totalArea([new Square(2), new Circle(1)])).toBeGreaterThan(4);
  });
});
