import sys
import os
import datetime
from datetime import timedelta
import json

# Add the path to your local modified version of birdsong
sys.path.insert(0, 'C:/VS Code/birdsong')  # Update this path to your local directory

# Import the specific classes you need
from birdsong.view import CanaryView
from birdsong.values import Tvq

def print_separator(title):
    print(f"\n{'='*50}")
    print(f"{title}")
    print(f"{'='*50}")

def test_new_functions():
    print_separator("Testing New API Functions")

    try:
        # Create the view object with explicit parameters
        view = CanaryView(
            host='', #your internal canary url
            https=True,
            httpsPort="" #specified port for view read api (55236, etc)
        )

        # Use a try-finally block to ensure proper cleanup
        try:
            # First try to browse nodes to find valid tags
            print("Looking for valid tags to test with...")

            try:
                # Try to find some tags by browsing
                all_tags = []
                for node in view.browseNodes():
                    print(f"Found node: {node}")
                    for dataset in view.browseNodes(node):
                        path = f"{node}.{dataset}"
                        print(f"Found dataset: {path}")
                        tags = list(view.browseTags(path))
                        if tags:
                            all_tags.extend(tags[:3])  # Get up to 3 tags
                            print(f"Found tags: {tags[:3]}")
                            break
                    if all_tags:
                        break
            except Exception as e:
                print(f"Error browsing for tags: {str(e)}")
                all_tags = []

            # If we couldn't find tags through browsing, use the ones from the test notebook
            if not all_tags:
                print("Using predefined test tags...")
                all_tags = [
                    "CS-Surface61.Testing.SAWQUY",
                    "CS-Surface61.Testing.TDONAZ",
                    "CS-Surface61.Testing.VIYIOL"
                ]

            # 1. Test getTagData2
            print("\nTesting getTagData2...")
            try:
                end_time = datetime.datetime.now()
                start_time = end_time - timedelta(hours=1)

                # Test with a single tag
                tag = all_tags[0]
                print(f"Getting data for single tag with getTagData2: {tag}")
                values = view.getTagData2(tag,
                                         start=start_time.isoformat(),
                                         end=end_time.isoformat(),
                                         maxSize=100)

                print(f"Retrieved {len(values)} values")
                for i, value in enumerate(values[:3]):
                    print(f"  {i+1}: {value}")

                # Test with multiple tags
                tags = all_tags[:2]
                print(f"\nGetting data for multiple tags with getTagData2: {tags}")
                results = view.getTagData2(tags,
                                         start=start_time.isoformat(),
                                         end=end_time.isoformat(),
                                         maxSize=100)

                for tag_path, values in results:
                    print(f"Tag: {tag_path}")
                    print(f"Retrieved {len(values)} values")
                    for i, value in enumerate(values[:3]):
                        print(f"  {i+1}: {value}")
            except Exception as e:
                print(f"Error testing getTagData2: {str(e)}")

            # 2. Test getTagData with new parameters
            print("\nTesting getTagData with new parameters...")
            try:
                tag = all_tags[0]
                print(f"Getting data with useTimeExtension=False: {tag}")
                values = view.getTagData(tag,
                                        useTimeExtension=False)

                print(f"Retrieved {len(values)} values with useTimeExtension=False")
                for i, value in enumerate(values[:3]):
                    print(f"  {i+1}: {value}")

                print(f"\nGetting data with quality='good': {tag}")
                values = view.getTagData(tag,
                                        quality='good')

                print(f"Retrieved {len(values)} values with quality='good'")
                for i, value in enumerate(values[:3]):
                    print(f"  {i+1}: {value}")
            except Exception as e:
                print(f"Error testing getTagData with new parameters: {str(e)}")

            # 3. Test getAnnotations
            print("\nTesting getAnnotations...")
            try:
                tag = all_tags[0]
                end_time = datetime.datetime.now()
                start_time = end_time - timedelta(days=30)

                print(f"Getting annotations for single tag: {tag}")
                annotations = view.getAnnotations(tag,
                                                start_time.isoformat(),
                                                end_time.isoformat())

                print(f"Retrieved annotations: {annotations}")

                # Test with multiple tags
                tags = all_tags[:2]
                print(f"\nGetting annotations for multiple tags: {tags}")
                results = view.getAnnotations(tags,
                                            start_time.isoformat(),
                                            end_time.isoformat())

                print(f"Retrieved annotations: {results}")
            except Exception as e:
                print(f"Error testing getAnnotations: {str(e)}")

            # 4. Test getTagContext
            print("\nTesting getTagContext...")
            try:
                tag = all_tags[0]
                print(f"Getting context for single tag: {tag}")
                context = view.getTagContext(tag)

                print(f"Retrieved context: {context}")

                # Test with multiple tags
                tags = all_tags[:2]
                print(f"\nGetting context for multiple tags: {tags}")
                contexts = view.getTagContext(tags)

                print(f"Retrieved contexts: {contexts}")
            except Exception as e:
                print(f"Error testing getTagContext: {str(e)}")

            return True
        finally:
            # Manually clean up resources
            try:
                view._revokeLiveDataToken()
            except:
                pass
            try:
                view._revokeUserToken()
            except:
                pass
    except Exception as e:
        print(f"Error in test: {str(e)}")
        return False

if __name__ == "__main__":
    # Disable SSL warnings if using self-signed certificates
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except:
        pass

    success = test_new_functions()
    print("\nTest completed " + ("successfully" if success else "with errors"))