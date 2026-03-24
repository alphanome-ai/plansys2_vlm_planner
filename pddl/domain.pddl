(define (domain single_robot_construction_xyz)

(:requirements :strips :typing :adl :fluents :durative-actions)

(:types
    robot box location
    x_coord y_coord z_coord
)

(:predicates
    ;; Robot state
    (robot_at ?r - robot ?l - location)
    (hand_empty ?r - robot)
    (holding ?r - robot ?b - box)

    ;; Box state
    (box_in_pickup_zone ?b - box ?l - location)
    (box_at_xyz ?b - box ?x - x_coord ?y - y_coord ?z - z_coord)

    ;; Coordinate and grid state
    (connected ?l1 - location ?l2 - location)
    (location_matches_xy ?l - location ?x - x_coord ?y - y_coord)
    (xyz_free ?x - x_coord ?y - y_coord ?z - z_coord)
    (xyz_occupied ?x - x_coord ?y - y_coord ?z - z_coord)

    ;; Stacking logic
    (is_ground_level ?z - z_coord)
    (z_above ?z_top - z_coord ?z_below - z_coord)
)

;; Navigate between locations.
;; Navigation is handled autonomously by the robot; move is kept for
;; planner completeness but generates no DAG task.
(:durative-action move
    :parameters (?r - robot ?from - location ?to - location)
    :duration ( = ?duration 10)
    :condition (and
        (at start (robot_at ?r ?from))
        (over all (connected ?from ?to))
    )
    :effect (and
        (at start (not (robot_at ?r ?from)))
        (at end (robot_at ?r ?to))
    )
)

;; Pick a box from its pickup zone.
;; The robot must remain at the pickup location for the full duration.
(:durative-action pick
    :parameters (?r - robot ?b - box ?l - location)
    :duration ( = ?duration 5)
    :condition (and
        (over all (robot_at ?r ?l))
        (at start (box_in_pickup_zone ?b ?l))
        (at start (hand_empty ?r))
    )
    :effect (and
        (at start (not (hand_empty ?r)))
        (at start (not (box_in_pickup_zone ?b ?l)))
        (at end (holding ?r ?b))
    )
)

;; Place a box directly on the ground (z must be ground level).
;; Slot at (x, y, z) must be free and will be marked occupied on completion.
(:durative-action place_ground
    :parameters (?r - robot ?b - box ?l - location ?x - x_coord ?y - y_coord ?z - z_coord)
    :duration ( = ?duration 5)
    :condition (and
        (at start (holding ?r ?b))
        (over all (robot_at ?r ?l))
        (over all (location_matches_xy ?l ?x ?y))
        (over all (is_ground_level ?z))
        (at start (xyz_free ?x ?y ?z))
    )
    :effect (and
        (at start (not (holding ?r ?b)))
        (at start (not (xyz_free ?x ?y ?z)))
        (at end (xyz_occupied ?x ?y ?z))
        (at end (hand_empty ?r))
        (at end (box_at_xyz ?b ?x ?y ?z))
    )
)

;; Place a box on top of an already-placed box (?b_below).
;; z_top must be directly above z_below via z_above.
;; The slot at z_top must be free; the slot at z_below must be occupied.
;; NOTE: ?b_below is an explicit parameter so the planner knows exactly
;; which box is the support — this must match the problem file objects.
(:durative-action place_stacked
    :parameters (?r - robot ?b - box ?b_below - box ?l - location
                 ?x - x_coord ?y - y_coord ?z_top - z_coord ?z_below - z_coord)
    :duration ( = ?duration 5)
    :condition (and
        (at start (holding ?r ?b))
        (over all (robot_at ?r ?l))
        (over all (location_matches_xy ?l ?x ?y))
        (over all (z_above ?z_top ?z_below))
        (at start (xyz_free ?x ?y ?z_top))
        (over all (box_at_xyz ?b_below ?x ?y ?z_below))
    )
    :effect (and
        (at start (not (holding ?r ?b)))
        (at start (not (xyz_free ?x ?y ?z_top)))
        (at end (xyz_occupied ?x ?y ?z_top))
        (at end (hand_empty ?r))
        (at end (box_at_xyz ?b ?x ?y ?z_top))
    )
)

)
