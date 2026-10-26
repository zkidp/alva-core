// Host-owned behavioral assertions shared by both paths, not an AIR predicate.
#[cfg(test)]
mod independent_behavior {
    use super::{demo_app, demo_model};

    #[test]
    fn application_compatibility() {
        assert_eq!(demo_app::run(), 6);
    }

    #[test]
    fn signed_delta_and_metadata() {
        for (size, delta, expected) in [(5, 7, 12), (5, 0, 5), (5, -3, 2), (-9, 4, -5)] {
            let m = demo_model::make_meta("key".into(), size, "tag".into());
            let changed = demo_model::touch_size(m, delta);
            assert_eq!(changed.size, expected);
            assert_eq!(changed.key, "key");
            assert_eq!(changed.etag, "tag");
        }
    }

    #[test]
    fn repeated_adjustment() {
        let m = demo_model::make_meta("repeat".into(), 10, "v1".into());
        let m = demo_model::touch_size(m, -4);
        let m = demo_model::touch_size(m, 9);
        assert_eq!(m.size, 15);
        assert_eq!(m.key, "repeat");
        assert_eq!(m.etag, "v1");
    }
}
