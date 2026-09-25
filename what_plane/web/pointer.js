const Pointer = (() => {
  const DEG = Math.PI / 180;
  const FULL_SCALE_DEG = 30;
  const LOCK_DEG = 10;
  const FT_TO_M = 0.3048;

  function elevationDeg(distanceKm, altitudeFt, observerAltM = 0) {
    const altM = altitudeFt * FT_TO_M - observerAltM;
    return Math.atan2(altM, distanceKm * 1000) / DEG;
  }

  function wrap180(deg) {
    return ((((deg + 180) % 360) + 360) % 360) - 180;
  }

  function enuVector(bearingDeg, elevationDegValue) {
    const az = bearingDeg * DEG;
    const el = elevationDegValue * DEG;
    const horiz = Math.cos(el);
    return {
      east: horiz * Math.sin(az),
      north: horiz * Math.cos(az),
      up: Math.sin(el),
    };
  }

  // W3C DeviceOrientationEvent worked example: device frame → Earth ENU.
  function deviceRotationMatrix(alpha, beta, gamma) {
    const x = (beta ?? 0) * DEG;
    const y = (gamma ?? 0) * DEG;
    const z = (alpha ?? 0) * DEG;
    const cX = Math.cos(x);
    const cY = Math.cos(y);
    const cZ = Math.cos(z);
    const sX = Math.sin(x);
    const sY = Math.sin(y);
    const sZ = Math.sin(z);
    return [
      cZ * cY - sZ * sX * sY,
      -cX * sZ,
      cY * sZ * sX + cZ * sY,
      cY * sZ + cZ * sX * sY,
      cZ * cX,
      sZ * sY - cZ * cY * sX,
      -cX * sY,
      sX,
      cX * cY,
    ];
  }

  function deviceFromEnu(matrix, enu) {
    return {
      x: matrix[0] * enu.east + matrix[3] * enu.north + matrix[6] * enu.up,
      y: matrix[1] * enu.east + matrix[4] * enu.north + matrix[7] * enu.up,
      z: matrix[2] * enu.east + matrix[5] * enu.north + matrix[8] * enu.up,
    };
  }

  function atan2deg(y, x) {
    return Math.atan2(y, x) / DEG;
  }

  function clampScale(deg) {
    return Math.max(-FULL_SCALE_DEG, Math.min(FULL_SCALE_DEG, deg));
  }

  function cdiDeviations({
    alpha,
    beta,
    gamma,
    headingDeg,
    bearingDeg,
    elevationDeg: el,
  }) {
    const matrix = deviceRotationMatrix(alpha, beta, gamma);
    const enu = enuVector(bearingDeg, el || 0);
    const device = deviceFromEnu(matrix, enu);
    const forward = -device.z;
    const behind = Math.abs(wrap180(bearingDeg - headingDeg)) > 90;
    const denom = Math.max(forward, 1e-6);
    let loc = atan2deg(device.x, denom);
    let gs = atan2deg(device.y, denom);

    if (behind) {
      const turn = wrap180(bearingDeg - headingDeg);
      loc = Math.sign(turn) * FULL_SCALE_DEG;
    }

    const locRaw = loc;
    const gsRaw = gs;
    loc = clampScale(loc);
    gs = clampScale(gs);
    const locked = !behind && Math.abs(locRaw) < LOCK_DEG && Math.abs(gsRaw) < LOCK_DEG;
    return { loc, gs, locRaw, gsRaw, behind, locked };
  }

  function cdiCaption({ locRaw, gsRaw, behind, locked }) {
    if (locked) return "Looking at it";
    if (behind) return "Turn around";
    if (Math.abs(locRaw) >= Math.abs(gsRaw)) {
      return locRaw > 0 ? "Turn right" : "Turn left";
    }
    return gsRaw > 0 ? "Look up" : "Look down";
  }

  return {
    FULL_SCALE_DEG,
    LOCK_DEG,
    elevationDeg,
    wrap180,
    enuVector,
    deviceRotationMatrix,
    cdiDeviations,
    cdiCaption,
  };
})();
