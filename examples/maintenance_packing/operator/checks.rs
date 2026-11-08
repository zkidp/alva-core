// Public operator-owned requirement/regression checks, not model ground truth.
#[test]
fn packing_requirement() {
    for (units, size, expected) in [
        (0, 4, 0), (1, 4, 1), (4, 4, 1), (5, 4, 2),
        (9, 4, 3), (i64::MAX, 1, i64::MAX),
        (i64::MAX, 2, 4_611_686_018_427_387_904),
    ] {
        assert_eq!(crate::model::packs_required(units, size), expected,
                   "units={units}, pack_size={size}");
        assert_eq!(crate::app::order_packs(units, size), expected);
    }
}

#[test]
fn protected_helper_regression() {
    for (units, size, expected) in [(0, 4, 0), (1, 4, 0), (4, 4, 4),
                                   (9, 4, 8), (i64::MAX, 2, i64::MAX - 1)] {
        assert_eq!(crate::model::full_pack_units(units, size), expected);
    }
}
