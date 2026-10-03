import * as Cesium from 'cesium'

/**
 * Coordinate Frame Transformation Helper for 3D Globe Visualization.
 *
 * NOTE: The backend D-DATO screening engine returns Cartesian state vectors
 * in the TEME (True Equator Mean Equinox) inertial frame with coordinates in kilometers.
 *
 * Cesium's 3D globe display is Earth-fixed (pseudo-fixed).
 * This function performs the display transformation:
 *   TEME (km) -> TEME (m) -> Cesium pseudo-fixed frame (m)
 * using Cesium.Transforms.computeTemeToPseudoFixedMatrix(julianDate).
 *
 * Caveat: Cesium's documented transform treats UT1 as equivalent to UTC.
 * This is a visualization-only transformation and DOES NOT alter backend scientific data.
 *
 * @param x_km TEME X coordinate in kilometers
 * @param y_km TEME Y coordinate in kilometers
 * @param z_km TEME Z coordinate in kilometers
 * @param isoTime UTC ISO 8601 timestamp string or Cesium.JulianDate
 * @returns Cesium.Cartesian3 in the pseudo-fixed frame (meters) for globe display
 */
export function temeKmToCesiumFixed(
  x_km: number,
  y_km: number,
  z_km: number,
  isoTime: string | Cesium.JulianDate
): Cesium.Cartesian3 {
  const julianDate =
    typeof isoTime === 'string'
      ? Cesium.JulianDate.fromIso8601(isoTime)
      : isoTime

  if (
    typeof x_km !== 'number' ||
    typeof y_km !== 'number' ||
    typeof z_km !== 'number' ||
    Number.isNaN(x_km) ||
    Number.isNaN(y_km) ||
    Number.isNaN(z_km)
  ) {
    throw new Error(
      `Invalid TEME coordinates: x_km=${x_km}, y_km=${y_km}, z_km=${z_km}. Expected valid numbers.`
    )
  }

  // Convert kilometers to meters for Cesium internal Cartesian3
  const x_m = x_km * 1000.0
  const y_m = y_km * 1000.0
  const z_m = z_km * 1000.0
  const temePositionMeters = new Cesium.Cartesian3(x_m, y_m, z_m)

  // Compute rotation matrix from TEME to Cesium pseudo-fixed frame at this epoch
  const temeToPseudoFixedMatrix =
    Cesium.Transforms.computeTemeToPseudoFixedMatrix(julianDate)

  if (!temeToPseudoFixedMatrix) {
    return temePositionMeters
  }

  return Cesium.Matrix3.multiplyByVector(
    temeToPseudoFixedMatrix,
    temePositionMeters,
    new Cesium.Cartesian3()
  )
}
