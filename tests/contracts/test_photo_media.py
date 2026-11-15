"""Photo-import stimuli (docs/changes/2026-11-15-photo-quiz-import): JPEG and higher limits only in photo mode."""
import base64
import hashlib
import struct
import zlib

import pytest

from studyez_contracts.roots import media

SHA = '0' * 64


def png(width=2, height=1):
    raw = b''.join(b'\x00' + b'\x00\x00\x00' * width for _ in range(height))
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def jpeg(width=3, height=2):
    # SOI, APP0(JFIF), SOF0 (one component), SOS header, one byte of scan data, EOI.
    app0 = b'\xff\xe0' + struct.pack('>H', 16) + b'JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    sof = b'\xff\xc0' + struct.pack('>HBHHB', 11, 8, height, width, 1) + b'\x01\x11\x00'
    sos = b'\xff\xda' + struct.pack('>HB', 8, 1) + b'\x01\x00\x00\x3f\x00'
    return b'\xff\xd8' + app0 + sof + sos + b'\x00' + b'\xff\xd9'


def stim(body, width, height):
    return {'source_id': 'S1', 'source_sha256': SHA, 'page': 1, 'crop': [0, 0, 1, 1],
            'sha256': hashlib.sha256(body).hexdigest(), 'width': width, 'height': height,
            'png_base64': base64.b64encode(body).decode()}


def bank(*stimuli):
    return {'questions': [{'question_id': f'Q{i}', 'stimuli': [s]} for i, s in enumerate(stimuli)]}


def test_jpeg_is_rejected_outside_photo_mode():
    with pytest.raises(ValueError, match='invalid PNG'):
        media.validate_images(bank(stim(jpeg(), 3, 2)))


def test_jpeg_is_accepted_in_photo_mode_and_checks_dimensions():
    media.validate_images(bank(stim(jpeg(), 3, 2)), photo=True)
    with pytest.raises(ValueError, match='dimensions mismatch'):
        media.validate_images(bank(stim(jpeg(), 4, 2)), photo=True)
    with pytest.raises(ValueError, match='invalid JPEG'):
        media.validate_images(bank(stim(jpeg()[:-2], 3, 2)), photo=True)


def test_png_still_validates_in_both_modes():
    for photo in (False, True):
        media.validate_images(bank(stim(png(), 2, 1)), photo=photo)


def test_photo_mode_raises_only_the_count_limit_it_names():
    many = [stim(png(), 2, 1) for _ in range(media.MAX_COUNT + 1)]
    with pytest.raises(ValueError, match='total limit'):
        media.validate_images(bank(*many))
    media.validate_images(bank(*many), photo=True)
    too_many = [stim(png(), 2, 1) for _ in range(media.PHOTO_MAX_COUNT + 1)]
    with pytest.raises(ValueError, match='total limit'):
        media.validate_images(bank(*too_many), photo=True)


def test_public_url_names_the_real_media_type():
    q = {'stimuli': [stim(jpeg(), 3, 2), stim(png(), 2, 1)]}
    urls = [i['url'] for i in media.public_images(q)]
    assert urls[0].startswith('data:image/jpeg;base64,') and urls[1].startswith('data:image/png;base64,')
