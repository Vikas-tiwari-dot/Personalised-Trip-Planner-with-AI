import time
import geocoder
from geopy.distance import geodesic
import logging

# ---------------- CONFIG ----------------
MONITORING_INTERVAL = 4 * 60 * 60  # 4 hours
DISTANCE_THRESHOLD_KM = 50
LOG_FILE = "trip_monitor.log"
# ----------------------------------------

# Setup logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

previous_location = None

def get_current_location():
    """Get your current coordinates automatically."""
    g = geocoder.ip('me')
    if g.ok:
        lat, lon = g.latlng
        print(f"Current location: Latitude {lat:.4f}, Longitude {lon:.4f}")
        return (lat, lon)
    else:
        print("Could not determine your location at this moment.")
        logging.warning("Failed to get current location.")
        return None

def check_for_trip(current_location, previous_location):
    """Check if you moved more than the threshold distance."""
    if previous_location is None:
        print("Setting your starting location. Monitoring will start from here.")
        logging.info(f"Initial location set at {current_location}")
        return False

    distance = geodesic(current_location, previous_location).km
    print(f"Distance traveled since last check: {distance:.2f} km")
    logging.info(f"Distance traveled: {distance:.2f} km")

    return distance > DISTANCE_THRESHOLD_KM

def main():
    global previous_location
    print("Trip Monitor Started")
    print("Monitoring your location every 4 hours.\n")
    logging.info("Trip Monitor Started")

    # Get the initial location
    previous_location = get_current_location()
    if previous_location is None:
        print("Unable to get initial location. Exiting.")
        return
    logging.info(f"Initial coordinates: {previous_location}")

    while True:
        print(f"\nWaiting {MONITORING_INTERVAL // 3600} hours before the next check...")
        time.sleep(MONITORING_INTERVAL)

        print("\nChecking your location now...")
        current_location = get_current_location()
        if current_location is None:
            print("Skipping this check due to location error.")
            continue

        if check_for_trip(current_location, previous_location):
            print("You have moved more than 50 km. Are you on a trip?")
            print("Enter 1 to confirm, or 0 to exit.")
            response = input("Your choice: ").strip()
            if response == '0':
                print("Stopping the monitor. Goodbye!")
                logging.info("Trip Monitor Stopped by User")
                break
            else:
                print("Acknowledged. Enjoy your trip!")
                logging.info(f"User confirmed trip at {current_location}")
        else:
            print("You are still within 50 km of the last location. Monitoring will continue.")

        # Update reference location
        previous_location = current_location
        logging.info(f"Reference location updated to {previous_location}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTrip Monitor stopped by user.")
        logging.info("Trip Monitor Stopped by User")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        logging.error(f"Unexpected error: {e}")