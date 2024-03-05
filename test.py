from airflow.decorators import dag, task
from airflow.utils.dates import days_ago
import logging
from typing import List, Dict
log = logging.getLogger(__name__)

# Simulating place/photo data
PLACE_PHOTOS = {
    "place_1": ["photo_1.1", "photo_1.2", "photo_1.3"],
    "place_2": [],
    "place_3": ["photo_3.1", "photo_3.2"],
}

def debug(*args):
    """Helper function for debugging"""
    print(*args)
    log.info(' '.join(map(str,args)))

@dag(schedule_interval=None, start_date=days_ago(1), catchup=False)
def test_expand_dag():

    @task
    def task_place_ids_list() -> List[str]:
        """Get a list of place IDs"""
        debug("task_place_ids_list")
        return list(PLACE_PHOTOS.keys())

    @task
    def task_place_photos_list(place_id) -> Dict[str, list]:
        """Get details for a place given its ID"""
        debug("task_place_photos_list")
        debug("place_id:", place_id)
        return {"id": place_id, "photos": PLACE_PHOTOS[place_id]}

    @task
    def task_combine_photos(places) -> List[str]:
        """Combine place photos into a single list"""
        debug("task_combine_photos")
        combined_photos = []
        for place in places:
            combined_photos.extend(place["photos"])
        return combined_photos
    
    @task
    def task_photo_process(photo) -> None:
        """Process a single photo"""
        debug("task_photo_process")
        debug("photo:", photo)
        pass

    # Retrieve lists
    place_ids = task_place_ids_list()
    places = task_place_photos_list.expand(place_id=place_ids)
    combined_photos = task_combine_photos(places)

    # Process photos using expand
    task_photo_process.expand(photo=combined_photos)

test_dag = test_expand_dag()