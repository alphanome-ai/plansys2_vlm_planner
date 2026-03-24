(define (problem stack_two_boxes_center)
(:domain single_robot_construction_xyz)

(:objects
    r1 - robot
    
    ;; The 8 ArUco boxes
    box26 box27 box28 box29 box30 box31 box32 box33 - box
    
    ;; 2D Navigation nodes for the robot
    loc_start loc_pickup loc_center - location
    
    ;; 3D Coordinates mapped to your 20x20x20 sizing
    x_center - x_coord
    y_center - y_coord
    z0 z20 - z_coord  ;; z0 = ground, z20 = 20 units high
)

(:init
    ;; --- Robot Initial State ---
    (hand_empty r1)
    (robot_at r1 loc_start)
    
    ;; --- Navigation Graph ---
    ;; Robot can move between the start, pickup area, and the center of the map
    (connected loc_start loc_pickup)
    (connected loc_pickup loc_center)
    (connected loc_center loc_pickup)
    
    ;; --- Box Initial State ---
    ;; All boxes start in the pickup zone
    (box_in_pickup_zone box26 loc_pickup)
    (box_in_pickup_zone box27 loc_pickup)
    (box_in_pickup_zone box28 loc_pickup)
    (box_in_pickup_zone box29 loc_pickup)
    (box_in_pickup_zone box30 loc_pickup)
    (box_in_pickup_zone box31 loc_pickup)
    (box_in_pickup_zone box32 loc_pickup)
    (box_in_pickup_zone box33 loc_pickup)
    
    ;; --- Coordinate & Spatial Mapping ---
    ;; Link the 2D location "loc_center" to the explicit X, Y coordinates
    (location_matches_xy loc_center x_center y_center)
    
    ;; Define the ground and the stacking heights (20 unit increments)
    (is_ground_level z0)
    (z_above z20 z0) 
    
    ;; Initialize the grid spaces at the center as empty and ready for placement
    (xyz_free x_center y_center z0)
    (xyz_free x_center y_center z20)
)

(:goal (and
    ;; Stack box26 on the ground at the center
    (box_at_xyz box26 x_center y_center z0)
    
    ;; Stack box27 directly on top of box26
    (box_at_xyz box27 x_center y_center z20)
))
)