# Geolocation Service Implementation Guide

## Overview

This guide covers the geolocation service including GPS coordinate handling, distance calculation using the Haversine formula, geofence management, and the admin location setup flow.

---

## Prerequisites

- Database models implemented (01_DATABASE_SCHEMA.md)
- Bot core setup completed (02_BOT_CORE.md)
- User management implemented (03_USER_MANAGEMENT.md)

---

## Geofence Concept

```
                     Office Location
                          (O)
                           *
                          /|\
                         / | \
                        /  |  \
                       /   |   \
                      / R=50m  \
                     /     |     \
                    *------+------*
                   /       |       \
                  /        |        \
                 *---------+---------*
                
    User A (30m) ✓    User B (45m) ✓    User C (80m) ✗
    Within radius     Within radius     Outside radius
```

The geofence is a circular area around the office location. Users must be within the radius to check in successfully.

---

## Haversine Formula

The Haversine formula calculates the great-circle distance between two points on a sphere given their latitudes and longitudes.

```
a = sin²(Δφ/2) + cos(φ1) × cos(φ2) × sin²(Δλ/2)
c = 2 × atan2(√a, √(1-a))
d = R × c

Where:
- φ = latitude (in radians)
- λ = longitude (in radians)
- R = Earth's radius (6,371 km or 6,371,000 m)
- d = distance between points
```

---

## Implementation Steps

### Step 1: Create Geolocation Service

**File: `src/services/geolocation.py`**

```python
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
from typing import Optional, List, Tuple
from dataclasses import dataclass

from src.database import Location, get_db_session
from src.config import config

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
        lon2: float
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
            math.sin(delta_lat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) *
            math.sin(delta_lon / 2) ** 2
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
        radius_meters: float
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
        radius: int,
        created_by: int
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
            raise ValueError(f"Invalid latitude: {latitude}")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Invalid longitude: {longitude}")
        if radius <= 0:
            raise ValueError(f"Radius must be positive: {radius}")
        
        with get_db_session() as db:
            location = Location(
                name=name,
                latitude=latitude,
                longitude=longitude,
                radius=radius,
                is_active=True,
                created_by=created_by
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
            location = db.query(Location).filter(
                Location.id == location_id
            ).first()
            
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
            locations = db.query(Location).filter(
                Location.is_active == True
            ).all()
            
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
    def update_location(
        location_id: int,
        name: str = None,
        latitude: float = None,
        longitude: float = None,
        radius: int = None,
        is_active: bool = None
    ) -> bool:
        """
        Update a location's details.
        
        Args:
            location_id: ID of location to update
            name: New name (optional)
            latitude: New latitude (optional)
            longitude: New longitude (optional)
            radius: New radius (optional)
            is_active: New active status (optional)
            
        Returns:
            True if updated, False if location not found
        """
        with get_db_session() as db:
            location = db.query(Location).filter(
                Location.id == location_id
            ).first()
            
            if not location:
                return False
            
            if name is not None:
                location.name = name
            if latitude is not None:
                location.latitude = latitude
            if longitude is not None:
                location.longitude = longitude
            if radius is not None:
                location.radius = radius
            if is_active is not None:
                location.is_active = is_active
            
            logger.info(f"Updated location {location_id}")
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
        return GeolocationService.update_location(
            location_id, is_active=False
        )
    
    @staticmethod
    def find_nearest_location(
        user_lat: float,
        user_lon: float
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
        min_distance = float('inf')
        
        for location in locations:
            distance = GeolocationService.haversine_distance(
                user_lat, user_lon,
                location.latitude, location.longitude
            )
            
            if distance < min_distance:
                min_distance = distance
                nearest = location
        
        return (nearest, min_distance) if nearest else None
    
    @staticmethod
    def check_location_for_checkin(
        user_lat: float,
        user_lon: float
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
                location=None
            )
        
        location, distance = result
        within_radius = distance <= location.radius
        
        return DistanceResult(
            distance_meters=distance,
            within_radius=within_radius,
            location=location
        )
    
    @staticmethod
    def format_coordinates(latitude: float, longitude: float) -> str:
        """
        Format coordinates as a human-readable string.
        
        Args:
            latitude: Latitude value
            longitude: Longitude value
            
        Returns:
            Formatted string like "21.0285°N, 105.8542°E"
        """
        lat_dir = "N" if latitude >= 0 else "S"
        lon_dir = "E" if longitude >= 0 else "W"
        
        return f"{abs(latitude):.6f}°{lat_dir}, {abs(longitude):.6f}°{lon_dir}"
    
    @staticmethod
    def get_google_maps_link(latitude: float, longitude: float) -> str:
        """
        Generate a Google Maps link for coordinates.
        
        Args:
            latitude: Latitude value
            longitude: Longitude value
            
        Returns:
            Google Maps URL
        """
        return f"https://www.google.com/maps?q={latitude},{longitude}"
```

### Step 2: Create Location Setup Handler (Admin)

**File: `src/bot/handlers/location.py`**

```python
"""
Location management handlers for admin users.

Handles setting up office locations via GPS coordinates.
"""

import logging
from telegram import Update, Message
from telegram.ext import (
    ContextTypes, 
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from src.services.geolocation import GeolocationService
from src.database import User
from src.constants import Messages, CallbackData
from src.bot.keyboards import Keyboards
from src.bot.middlewares import require_admin, log_action
from src.config import config

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_LOCATION = 1
WAITING_FOR_NAME = 2
WAITING_FOR_RADIUS = 3

# Temporary storage for location setup
location_setup_data = {}


@require_admin
@log_action("set_location_start")
async def set_location_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> int:
    """
    Handle /set_location command.
    
    Starts the location setup conversation.
    
    Returns:
        Conversation state WAITING_FOR_LOCATION
    """
    user_id = update.effective_user.id
    
    # Clear any previous setup data
    location_setup_data[user_id] = {}
    
    await update.message.reply_text(
        "Thiet lap dia diem van phong moi.\n\n"
        "Buoc 1/3: Vui long gui vi tri GPS cua van phong:",
        reply_markup=Keyboards.request_location()
    )
    
    return WAITING_FOR_LOCATION


async def receive_location_for_setup(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Receive GPS location for new office setup.
    
    Stores coordinates and asks for location name.
    
    Returns:
        Conversation state WAITING_FOR_NAME
    """
    user_id = update.effective_user.id
    location = update.message.location
    
    # Store coordinates
    location_setup_data[user_id] = {
        "latitude": location.latitude,
        "longitude": location.longitude
    }
    
    # Format for display
    coords = GeolocationService.format_coordinates(
        location.latitude, location.longitude
    )
    maps_link = GeolocationService.get_google_maps_link(
        location.latitude, location.longitude
    )
    
    await update.message.reply_text(
        f"Da nhan vi tri:\n{coords}\n\n"
        f"Xem tren Google Maps: {maps_link}\n\n"
        "Buoc 2/3: Vui long nhap ten cho dia diem nay\n"
        "(Vi du: VP Ha Noi, Chi nhanh HCM, ...):",
        reply_markup=Keyboards.remove()
    )
    
    return WAITING_FOR_NAME


async def receive_location_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Receive location name during setup.
    
    Stores name and asks for geofence radius.
    
    Returns:
        Conversation state WAITING_FOR_RADIUS
    """
    user_id = update.effective_user.id
    name = update.message.text.strip()
    
    # Validate name
    if len(name) < 2:
        await update.message.reply_text(
            "Ten qua ngan. Vui long nhap lai:"
        )
        return WAITING_FOR_NAME
    
    if len(name) > 100:
        await update.message.reply_text(
            "Ten qua dai. Vui long nhap lai (toi da 100 ky tu):"
        )
        return WAITING_FOR_NAME
    
    # Store name
    location_setup_data[user_id]["name"] = name
    
    await update.message.reply_text(
        f"Ten dia diem: {name}\n\n"
        f"Buoc 3/3: Vui long nhap ban kinh cho phep (met)\n"
        f"(Khoang cach toi da tu van phong de check-in thanh cong)\n\n"
        f"Vi du: 50 (cho phep check-in trong vong 50 met)\n"
        f"Mac dinh: {config.attendance.default_radius}m"
    )
    
    return WAITING_FOR_RADIUS


async def receive_radius(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Receive geofence radius and complete location setup.
    
    Creates the location in database and confirms to admin.
    
    Returns:
        ConversationHandler.END
    """
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Parse radius
    try:
        radius = int(text)
        if radius <= 0:
            raise ValueError("Radius must be positive")
        if radius > 10000:  # Max 10km
            raise ValueError("Radius too large")
    except ValueError:
        await update.message.reply_text(
            "Gia tri khong hop le. Vui long nhap so nguyen duong (1-10000):"
        )
        return WAITING_FOR_RADIUS
    
    # Get stored data
    data = location_setup_data.get(user_id, {})
    
    if not data.get("latitude") or not data.get("name"):
        await update.message.reply_text(
            "Loi: Thieu du lieu. Vui long bat dau lai voi /set_location"
        )
        return ConversationHandler.END
    
    # Create location
    try:
        location = GeolocationService.create_location(
            name=data["name"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            radius=radius,
            created_by=user_id
        )
        
        # Clean up
        del location_setup_data[user_id]
        
        await update.message.reply_text(
            Messages.LOCATION_SET_SUCCESS.format(
                name=location.name,
                lat=location.latitude,
                lon=location.longitude,
                radius=location.radius
            ),
            reply_markup=Keyboards.admin_menu()
        )
        
        logger.info(
            f"Admin {user_id} created location: {location.name} "
            f"at ({location.latitude}, {location.longitude})"
        )
        
    except Exception as e:
        logger.error(f"Failed to create location: {e}")
        await update.message.reply_text(
            f"Loi khi tao dia diem: {str(e)}"
        )
    
    return ConversationHandler.END


async def cancel_location_setup(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Cancel location setup conversation."""
    user_id = update.effective_user.id
    
    # Clean up
    if user_id in location_setup_data:
        del location_setup_data[user_id]
    
    await update.message.reply_text(
        "Da huy thiet lap dia diem.",
        reply_markup=Keyboards.admin_menu()
    )
    
    return ConversationHandler.END


# Location setup conversation handler
location_setup_conversation = ConversationHandler(
    entry_points=[
        CommandHandler("set_location", set_location_command)
    ],
    states={
        WAITING_FOR_LOCATION: [
            MessageHandler(filters.LOCATION, receive_location_for_setup)
        ],
        WAITING_FOR_NAME: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                receive_location_name
            )
        ],
        WAITING_FOR_RADIUS: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                receive_radius
            )
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel_location_setup),
        MessageHandler(filters.COMMAND, cancel_location_setup)
    ],
    allow_reentry=True
)


# =============================================================================
# LOCATION LISTING & MANAGEMENT
# =============================================================================

@require_admin
async def list_locations_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /list_locations command.
    
    Lists all configured office locations.
    """
    locations = GeolocationService.get_all_locations()
    
    if not locations:
        await update.message.reply_text(
            "Chua co dia diem nao duoc cau hinh.\n"
            "Su dung /set_location de them dia diem moi."
        )
        return
    
    lines = ["📍 Danh sach dia diem:\n"]
    
    for loc in locations:
        status = "✅ Active" if loc.is_active else "❌ Inactive"
        coords = GeolocationService.format_coordinates(
            loc.latitude, loc.longitude
        )
        
        lines.append(
            f"\n{loc.id}. {loc.name}\n"
            f"   Toa do: {coords}\n"
            f"   Ban kinh: {loc.radius}m\n"
            f"   Trang thai: {status}"
        )
    
    await update.message.reply_text("\n".join(lines))


@require_admin
async def delete_location_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /delete_location <id> command.
    
    Deactivates a location.
    
    Usage: /delete_location 1
    """
    if not context.args:
        await update.message.reply_text(
            "Su dung: /delete_location <id>\n"
            "Vi du: /delete_location 1\n\n"
            "Dung /list_locations de xem danh sach ID."
        )
        return
    
    try:
        location_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID khong hop le.")
        return
    
    location = GeolocationService.get_location(location_id)
    
    if not location:
        await update.message.reply_text(f"Khong tim thay dia diem ID: {location_id}")
        return
    
    if GeolocationService.delete_location(location_id):
        await update.message.reply_text(
            f"Da vo hieu hoa dia diem: {location.name}"
        )
    else:
        await update.message.reply_text("Khong the xoa dia diem.")
```

### Step 3: Alternative Using geopy Library

If you prefer using the `geopy` library for more accurate calculations:

**File: `src/services/geolocation_geopy.py`**

```python
"""
Alternative geolocation service using geopy library.

Provides more accurate geodesic calculations and additional features.
"""

from geopy.distance import geodesic
from geopy.point import Point
from typing import Tuple, Optional

from src.database import Location, get_db_session


class GeolocationServiceGeopy:
    """Geolocation service using geopy library."""
    
    @staticmethod
    def calculate_distance(
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """
        Calculate distance between two points using geodesic (more accurate).
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in meters
        """
        point1 = (lat1, lon1)
        point2 = (lat2, lon2)
        
        # Returns distance in kilometers, convert to meters
        return geodesic(point1, point2).meters
    
    @staticmethod
    def is_within_radius(
        user_lat: float,
        user_lon: float,
        center_lat: float,
        center_lon: float,
        radius_meters: float
    ) -> Tuple[bool, float]:
        """
        Check if user is within radius using geodesic distance.
        """
        distance = GeolocationServiceGeopy.calculate_distance(
            user_lat, user_lon, center_lat, center_lon
        )
        return distance <= radius_meters, distance
    
    @staticmethod
    def get_bounding_box(
        center_lat: float,
        center_lon: float,
        radius_meters: float
    ) -> Tuple[float, float, float, float]:
        """
        Get bounding box coordinates for a circular area.
        
        Useful for initial filtering in database queries.
        
        Returns:
            Tuple of (min_lat, max_lat, min_lon, max_lon)
        """
        from geopy.distance import distance
        
        center = Point(center_lat, center_lon)
        
        # Calculate corners
        north = distance(meters=radius_meters).destination(center, bearing=0)
        south = distance(meters=radius_meters).destination(center, bearing=180)
        east = distance(meters=radius_meters).destination(center, bearing=90)
        west = distance(meters=radius_meters).destination(center, bearing=270)
        
        return (
            south.latitude,   # min_lat
            north.latitude,   # max_lat
            west.longitude,   # min_lon
            east.longitude    # max_lon
        )
```

---

## Testing Geolocation Service

```python
"""Test file: tests/test_geolocation.py"""

import pytest
import math
from src.services.geolocation import GeolocationService

def test_haversine_same_point():
    """Distance between same point should be 0."""
    distance = GeolocationService.haversine_distance(
        21.0285, 105.8542,
        21.0285, 105.8542
    )
    assert distance < 0.01  # Less than 1cm

def test_haversine_known_distance():
    """Test against known distance between two points."""
    # Hanoi to Ho Chi Minh City (approximately 1,150 km)
    distance = GeolocationService.haversine_distance(
        21.0285, 105.8542,   # Hanoi
        10.8231, 106.6297    # HCMC
    )
    # Should be approximately 1,150 km (1,150,000 m)
    assert 1_100_000 < distance < 1_200_000

def test_haversine_short_distance():
    """Test short distance calculation."""
    # Two points about 100 meters apart
    distance = GeolocationService.haversine_distance(
        21.0285, 105.8542,
        21.0294, 105.8542  # ~100m north
    )
    assert 90 < distance < 110

def test_within_radius_inside():
    """Test point inside radius."""
    within, distance = GeolocationService.is_within_radius(
        21.0286, 105.8543,  # User (slightly offset)
        21.0285, 105.8542,  # Center
        50  # 50m radius
    )
    assert within == True
    assert distance < 50

def test_within_radius_outside():
    """Test point outside radius."""
    within, distance = GeolocationService.is_within_radius(
        21.0300, 105.8542,  # User (~170m away)
        21.0285, 105.8542,  # Center
        50  # 50m radius
    )
    assert within == False
    assert distance > 50

def test_create_location():
    """Test location creation."""
    from src.database import init_db
    init_db("sqlite:///:memory:")
    
    location = GeolocationService.create_location(
        name="Test Office",
        latitude=21.0285,
        longitude=105.8542,
        radius=50,
        created_by=123
    )
    
    assert location.id is not None
    assert location.name == "Test Office"
    assert location.radius == 50
    assert location.is_active == True

def test_find_nearest_location():
    """Test finding nearest location."""
    from src.database import init_db
    init_db("sqlite:///:memory:")
    
    # Create two locations
    GeolocationService.create_location(
        "Office A", 21.0285, 105.8542, 50, 123
    )
    GeolocationService.create_location(
        "Office B", 21.0500, 105.8500, 50, 123
    )
    
    # Find nearest to Office A
    result = GeolocationService.find_nearest_location(21.0286, 105.8543)
    
    assert result is not None
    location, distance = result
    assert location.name == "Office A"
    assert distance < 100

def test_invalid_coordinates():
    """Test validation of invalid coordinates."""
    from src.database import init_db
    init_db("sqlite:///:memory:")
    
    with pytest.raises(ValueError):
        GeolocationService.create_location(
            "Invalid", 91.0, 105.0, 50, 123  # Latitude > 90
        )
    
    with pytest.raises(ValueError):
        GeolocationService.create_location(
            "Invalid", 21.0, 181.0, 50, 123  # Longitude > 180
        )
```

---

## Coordinate Reference

### Vietnam Major Cities Coordinates

| City | Latitude | Longitude |
|------|----------|-----------|
| Hanoi | 21.0285 | 105.8542 |
| Ho Chi Minh City | 10.8231 | 106.6297 |
| Da Nang | 16.0544 | 108.2022 |
| Hai Phong | 20.8449 | 106.6881 |
| Can Tho | 10.0452 | 105.7469 |

### Approximate Distances

| Distance (m) | Latitude Change | Longitude Change (at equator) |
|--------------|-----------------|------------------------------|
| 1 | 0.000009 | 0.000009 |
| 10 | 0.00009 | 0.00009 |
| 50 | 0.00045 | 0.00045 |
| 100 | 0.0009 | 0.0009 |
| 1000 | 0.009 | 0.009 |

*Note: Longitude change varies with latitude. At Vietnam's latitude (~10-21°N), multiply by ~0.9-1.0*

---

## Verification Checklist

Before proceeding to the next blueprint, verify:

- [ ] `src/services/geolocation.py` created with all methods
- [ ] `src/bot/handlers/location.py` created with admin handlers
- [ ] Haversine formula calculates distances correctly
- [ ] `is_within_radius` works for both inside and outside cases
- [ ] Location CRUD operations work
- [ ] `/set_location` conversation flow works
- [ ] `/list_locations` shows all locations
- [ ] `/delete_location` deactivates location
- [ ] Integration with check-in flow works

---

## Next Steps

Proceed to `06_ANTI_CHEAT.md` to implement fraud prevention measures.
