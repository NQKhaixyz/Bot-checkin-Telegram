"""
Geolocation service for GPS coordinate handling and distance calculation.

Provides functionality for:
- Distance calculation using Haversine formula
- Geofence validation
- Location management (CRUD)
- Finding nearest office location
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.database import Location, get_db_session

logger = logging.getLogger(__name__)

# Earth's radius in meters
EARTH_RADIUS_METERS = 6_371_000


@dataclass
class DistanceResult:
    """Result of a distance calculation."""

    distance_meters: float
    within_radius: bool
    location: Optional[Location] = None


class GeolocationService:
    """Service class for geolocation operations."""

    @staticmethod
    def haversine_distance(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """
        Calculate the great-circle distance between two GPS coordinates.

        Uses the Haversine formula to account for Earth's curvature.

        Args:
            lat1: Latitude of point 1 (degrees)
            lon1: Longitude of point 1 (degrees)
            lat2: Latitude of point 2 (degrees)
            lon2: Longitude of point 2 (degrees)

        Returns:
            Distance in meters

        Example:
            >>> GeolocationService.haversine_distance(21.0285, 105.8542, 21.0300, 105.8550)
            180.5  # approximately 180 meters
        """
        # Convert degrees to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        lon1_rad = math.radians(lon1)
        lon2_rad = math.radians(lon2)

        # Differences
        delta_lat = lat2_rad - lat1_rad
        delta_lon = lon2_rad - lon1_rad

        # Haversine formula
        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        # Distance in meters
        distance = EARTH_RADIUS_METERS * c

        return distance

    @staticmethod
    def is_within_radius(
        user_lat: float,
        user_lon: float,
        center_lat: float,
        center_lon: float,
        radius_meters: float,
    ) -> Tuple[bool, float]:
        """
        Check if a user's location is within a specified radius.

        Args:
            user_lat: User's latitude
            user_lon: User's longitude
            center_lat: Center point latitude (office location)
            center_lon: Center point longitude (office location)
            radius_meters: Allowed radius in meters

        Returns:
            Tuple of (is_within_radius, actual_distance_meters)

        Example:
            >>> GeolocationService.is_within_radius(21.0286, 105.8543, 21.0285, 105.8542, 50)
            (True, 15.3)  # Within 50m radius, actual distance is 15.3m
        """
        distance = GeolocationService.haversine_distance(
            user_lat, user_lon, center_lat, center_lon
        )

        return distance <= radius_meters, distance

    @staticmethod
    def create_location(
        name: str,
        latitude: float,
        longitude: float,
        radius: float,
        created_by: int,
    ) -> Location:
        """
        Create a new office location.

        Args:
            name: Location name (e.g., "VP Ha Noi")
            latitude: GPS latitude coordinate
            longitude: GPS longitude coordinate
            radius: Geofence radius in meters
            created_by: Admin user ID who created this location

        Returns:
            Created Location object

        Raises:
            ValueError: If coordinates are invalid
        """
        # Validate coordinates
        if not -90 <= latitude <= 90:
            raise ValueError(f"Invalid latitude: {latitude}. Must be between -90 and 90.")
        if not -180 <= longitude <= 180:
            raise ValueError(
                f"Invalid longitude: {longitude}. Must be between -180 and 180."
            )
        if radius <= 0:
            raise ValueError(f"Radius must be positive: {radius}")

        with get_db_session() as db:
            location = Location(
                name=name,
                latitude=latitude,
                longitude=longitude,
                radius=radius,
                is_active=True,
                created_by=created_by,
            )
            db.add(location)
            db.flush()

            # Expunge to use outside session
            db.expunge(location)

            logger.info(
                f"Created location: {name} at ({latitude}, {longitude}) "
                f"with radius {radius}m"
            )

            return location

    @staticmethod
    def get_location(location_id: int) -> Optional[Location]:
        """
        Get a location by ID.

        Args:
            location_id: Location ID

        Returns:
            Location object or None
        """
        with get_db_session() as db:
            location = db.query(Location).filter(Location.id == location_id).first()

            if location:
                db.expunge(location)

            return location

    @staticmethod
    def get_active_locations() -> List[Location]:
        """
        Get all active office locations.

        Returns:
            List of active Location objects
        """
        with get_db_session() as db:
            locations = db.query(Location).filter(Location.is_active == True).all()

            for loc in locations:
                db.expunge(loc)

            return locations

    @staticmethod
    def get_all_locations() -> List[Location]:
        """
        Get all locations (active and inactive).

        Returns:
            List of all Location objects
        """
        with get_db_session() as db:
            locations = db.query(Location).all()

            for loc in locations:
                db.expunge(loc)

            return locations

    @staticmethod
    def update_location(location_id: int, **kwargs) -> bool:
        """
        Update a location's details.

        Args:
            location_id: ID of location to update
            **kwargs: Fields to update (name, latitude, longitude, radius, is_active)

        Returns:
            True if updated, False if location not found

        Raises:
            ValueError: If invalid field values are provided
        """
        # Validate coordinates if provided
        if "latitude" in kwargs and kwargs["latitude"] is not None:
            if not -90 <= kwargs["latitude"] <= 90:
                raise ValueError(
                    f"Invalid latitude: {kwargs['latitude']}. Must be between -90 and 90."
                )
        if "longitude" in kwargs and kwargs["longitude"] is not None:
            if not -180 <= kwargs["longitude"] <= 180:
                raise ValueError(
                    f"Invalid longitude: {kwargs['longitude']}. Must be between -180 and 180."
                )
        if "radius" in kwargs and kwargs["radius"] is not None:
            if kwargs["radius"] <= 0:
                raise ValueError(f"Radius must be positive: {kwargs['radius']}")

        with get_db_session() as db:
            location = db.query(Location).filter(Location.id == location_id).first()

            if not location:
                return False

            # Update allowed fields
            allowed_fields = {"name", "latitude", "longitude", "radius", "is_active"}
            for key, value in kwargs.items():
                if key in allowed_fields and value is not None:
                    setattr(location, key, value)

            logger.info(f"Updated location {location_id}: {kwargs}")
            return True

    @staticmethod
    def delete_location(location_id: int) -> bool:
        """
        Delete (deactivate) a location.

        Soft delete by setting is_active to False.

        Args:
            location_id: ID of location to delete

        Returns:
            True if deleted, False if not found
        """
        return GeolocationService.update_location(location_id, is_active=False)

    @staticmethod
    def find_nearest_location(
        user_lat: float,
        user_lon: float,
    ) -> Optional[Tuple[Location, float]]:
        """
        Find the nearest active office location to user's coordinates.

        Args:
            user_lat: User's latitude
            user_lon: User's longitude

        Returns:
            Tuple of (Location, distance_meters) or None if no locations

        Example:
            >>> nearest = GeolocationService.find_nearest_location(21.0285, 105.8542)
            >>> if nearest:
            ...     location, distance = nearest
            ...     print(f"Nearest: {location.name} at {distance}m")
        """
        locations = GeolocationService.get_active_locations()

        if not locations:
            return None

        nearest = None
        min_distance = float("inf")

        for location in locations:
            distance = GeolocationService.haversine_distance(
                user_lat, user_lon, location.latitude, location.longitude
            )

            if distance < min_distance:
                min_distance = distance
                nearest = location

        return (nearest, min_distance) if nearest else None

    @staticmethod
    def check_location_for_checkin(
        user_lat: float,
        user_lon: float,
    ) -> DistanceResult:
        """
        Check if user can check in at any active location.

        Finds the nearest location and checks if user is within its radius.

        Args:
            user_lat: User's latitude
            user_lon: User's longitude

        Returns:
            DistanceResult with distance and validation info
        """
        result = GeolocationService.find_nearest_location(user_lat, user_lon)

        if not result:
            return DistanceResult(
                distance_meters=0,
                within_radius=False,
                location=None,
            )

        location, distance = result
        within_radius = distance <= location.radius

        return DistanceResult(
            distance_meters=distance,
            within_radius=within_radius,
            location=location,
        )

    @staticmethod
    def format_coordinates(lat: float, lon: float) -> str:
        """
        Format coordinates as a human-readable string.

        Args:
            lat: Latitude value
            lon: Longitude value

        Returns:
            Formatted string like "21.0285°N, 105.8542°E"
        """
        lat_dir = "N" if lat >= 0 else "S"
        lon_dir = "E" if lon >= 0 else "W"

        return f"{abs(lat):.4f}{lat_dir}, {abs(lon):.4f}{lon_dir}"

    @staticmethod
    def get_google_maps_link(lat: float, lon: float) -> str:
        """
        Generate a Google Maps link for coordinates.

        Args:
            lat: Latitude value
            lon: Longitude value

        Returns:
            Google Maps URL
        """
        return f"https://www.google.com/maps?q={lat},{lon}"
