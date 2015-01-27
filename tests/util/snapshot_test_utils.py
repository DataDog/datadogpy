import io

from PIL import Image
import nose.tools as nt

from datadog.util.compat import url_lib

# For Python3 compat
try:
    xrange
except NameError:
    xrange = range


def read_image_as_raster(img_url):
    """ Reads image data from URL in raster format."""
    img = url_lib.urlopen(img_url)
    image_file = io.BytesIO(img.read())
    img = Image.open(image_file)
    w, h = img.size
    pixels = img.load()
    return [pixels[x, y] for x in range(w) for y in xrange(h)]


def assert_snap_not_blank(snapshot_url):
    """ Asserts snapshot is not blank"""
    pixels = read_image_as_raster(snapshot_url)
    nt.ok_(pixels is not None
           and isinstance(pixels, list)
           and len(set(pixels)) > 2,
           msg="Invalid or blank snapshot: {0}".format(snapshot_url))
    for pixel in set(pixels):
        nt.ok_(isinstance(pixel, tuple),
               msg="Invalid snapshot: {0}".format(snapshot_url))


def assert_snap_has_no_events(snapshot_url):
    """ Asserts snapshot has no events"""
    pixels = read_image_as_raster(snapshot_url)
    for color in set(pixels):
        r, g, b, a = color  # red, green, blue, alpha
        nt.ok_(r != 255 or g != 230 and b != 230,
               msg="Snapshot should not have events: {0}".format(snapshot_url))
