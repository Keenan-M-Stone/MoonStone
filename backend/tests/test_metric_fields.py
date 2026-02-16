import uuid

import numpy as np


def test_metric_field_roundtrip_and_sampling():
    from app.metric_fields import MetricFieldMeta, save_metric_field, load_metric_field, sample_metric_field, delete_metric_field

    fid = f"test_field_{uuid.uuid4()}"
    try:
        meta = MetricFieldMeta(
            field_id=fid,
            origin=(0.0, 0.0, 0.0),
            spacing=(1.0, 1.0, 1.0),
            shape=(2, 2, 2),
        )

        # Build a simple metric grid where only g00 varies linearly with x+y+z.
        g = np.zeros((2, 2, 2, 4, 4), dtype=float)
        for ix in range(2):
            for iy in range(2):
                for iz in range(2):
                    val = float(ix + iy + iz)
                    m = np.diag([-1.0 - 0.1 * val, 1.0, 1.0, 1.0])
                    g[ix, iy, iz] = m

        save_metric_field(fid, meta, g)
        meta2, g2 = load_metric_field(fid)
        assert meta2.field_id == fid
        assert g2.shape == (2, 2, 2, 4, 4)

        # Center of the cube should average all corners.
        s = sample_metric_field((0.5, 0.5, 0.5), meta2, g2)
        assert s.shape == (4, 4)
        # Expected average val across 8 corners: mean(ix+iy+iz) for ix,iy,iz in {0,1} is 1.5
        expected_g00 = -1.0 - 0.1 * 1.5
        assert np.isfinite(s).all()
        assert np.allclose(s[0, 0], expected_g00, rtol=0, atol=1e-12)
        assert np.allclose(s[1:, 1:], np.eye(3), rtol=0, atol=1e-12)
    finally:
        delete_metric_field(fid)


def test_constitutive_at_supports_field_metric():
    from app.metric_fields import MetricFieldMeta, save_metric_field, delete_metric_field
    from app.metrics import constitutive_at, plebanski_mapping, flat_metric

    fid = f"test_field_flat_{uuid.uuid4()}"
    try:
        meta = MetricFieldMeta(
            field_id=fid,
            origin=(0.0, 0.0, 0.0),
            spacing=(1.0, 1.0, 1.0),
            shape=(2, 2, 2),
        )
        g_flat = flat_metric((0.0, 0.0, 0.0))
        g = np.zeros((2, 2, 2, 4, 4), dtype=float)
        g[:] = g_flat
        save_metric_field(fid, meta, g)

        out_field = constitutive_at((0.25, 0.25, 0.25), {'type': 'field', 'field_id': fid, 'mapping': 'sunstone'})
        out_ref = plebanski_mapping(g_flat)
        for k in ['eps', 'mu', 'xi', 'zeta']:
            assert np.allclose(out_field[k], out_ref[k], atol=1e-10, rtol=1e-10)
    finally:
        delete_metric_field(fid)


def test_generate_weakfield_metric_grid_sanity():
    from app.metric_fields import generate_weakfield_metric_grid

    # Single point mass at origin; evaluate a 2x1x1 grid at x=1 and x=2.
    g = generate_weakfield_metric_grid(
        origin=(1.0, 0.0, 0.0),
        spacing=(1.0, 1.0, 1.0),
        shape=(2, 1, 1),
        objects=[{'mass': 1.0, 'position': (0.0, 0.0, 0.0)}],
        softening=0.0,
        max_points=1024,
    )
    assert g.shape == (2, 1, 1, 4, 4)

    # Phi = -M/r; g00 = -(1 + 2Phi) = -(1 - 2M/r)
    g00_r1 = g[0, 0, 0, 0, 0]
    g00_r2 = g[1, 0, 0, 0, 0]
    assert np.isfinite(g00_r1)
    assert np.isfinite(g00_r2)
    # At r=1, -(1 - 2) = +1; at r=2, -(1 - 1) = -0.
    assert np.allclose(g00_r1, 1.0, atol=1e-12)
    assert np.allclose(g00_r2, -0.0, atol=1e-12)

    # Spatial metric should remain positive in this weak-field form.
    assert g[0, 0, 0, 1, 1] > 0
