%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Minimal 3D box placement model
% - Each box has (x,y,z) position
% - Rotation allowed (swap length/width)
% - No overlap
% - Inside container
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

include "globals.mzn";

% --------------------
% INPUT PARAMETERS
% --------------------

int: N;                           % number of boxes
set of int: BOXES = 1..N;

int: W; int: L; int: H;           % container dimensions (width, length, height)

array[BOXES] of int: len;         % box length
array[BOXES] of int: wid;         % box width
array[BOXES] of int: hgt;         % box height

% ---- NO OVERLAP with 5 cm buffer ----
int: BUF;

% --------------------
% DECISION VARIABLES
% --------------------

array[BOXES] of var 0..W: x;       % x-position
array[BOXES] of var 0..L: y;       % y-position
array[BOXES] of var 0..H: z;       % z-position

array[BOXES] of var 0..1: rot;     % 0 = normal, 1 = swapped rotation

array[BOXES] of var int: eff_len;  % effective length
array[BOXES] of var int: eff_wid;  % effective width


var 0..H: max_used_height;         % top of highest box

var 0..W: max_x_extent;
var 0..L: max_y_extent;

var int: cluster_score = sum(p in BOXES)(x[p] + y[p]);

% --------------------
% BOUNDING RECTANGLE OF STACKED BOXES TOGETHER
% --------------------

% constraint max_x_extent = max([ x[p] + eff_wid[p] | p in BOXES ]);
% constraint max_y_extent = max([ y[p] + eff_len[p] | p in BOXES ]);
% constraint max_used_height = max([ z[p] + hgt[p] | p in BOXES ]);

% --------------------
% ROTATION CONSTRAINT
% --------------------

constraint forall(p in BOXES) (
    (rot[p] = 0 -> eff_len[p] = len[p] /\ eff_wid[p] = wid[p]) /\
    (rot[p] = 1 -> eff_len[p] = wid[p] /\ eff_wid[p] = len[p])
);


% --------------------
% INSIDE CONTAINER
% --------------------

constraint forall(p in BOXES)(
    x[p] + eff_wid[p] <= W /\
    y[p] + eff_len[p] <= L /\
    z[p] + hgt[p]     <= H
);


% --------------------
% NO OVERLAP (5cm buffer, except when stacked)
% --------------------
constraint forall(p, q in BOXES where p < q)(
       x[p] + eff_wid[p] + BUF <= x[q] \/
       x[q] + eff_wid[q] + BUF <= x[p] \/
       y[p] + eff_len[p] + BUF <= y[q] \/
       y[q] + eff_len[q] + BUF <= y[p] \/
       z[p] + hgt[p] <= z[q] \/
       z[q] + hgt[q] <= z[p]
);

% --------------------
% NO LEVITATION  
% --------------------
% Pallet sits on the floor OR pallet p’s whole footprint is contained within pallet q’s footprint at exactly the height of q’s top. 

predicate is_supported_by(int: p, int: q) =
    z[p] = z[q] + hgt[q] /\
    x[p] >= x[q] /\
    x[p] + eff_wid[p] <= x[q] + eff_wid[q] /\
    y[p] >= y[q] /\
    y[p] + eff_len[p] <= y[q] + eff_len[q];
    

constraint forall(p in BOXES)(
    z[p] = 0
    \/
    exists(q in BOXES where q != p)(
        is_supported_by(p, q)
    )
);

% --------------------
% ENFORCE PUSHING TOWARDS THE ORIGIN
% --------------------

% constraint forall(p in BOXES)(
%    x[p] <= max_x_extent
%    /\ y[p] <= max_y_extent
% );


% --------------------
% MAX USED HEIGHT + OBJECTIVE
% --------------------

constraint max_used_height = max([ z[p] + hgt[p] | p in BOXES ]);

% solve minimize max_used_height;

solve minimize(
    1000 * max_used_height 
  + max_y_extent
  + max_x_extent
%   + cluster_score
  );



output [
  show(p) ++ "," ++
  show(x[p]) ++ "," ++
  show(y[p]) ++ "," ++
  show(z[p]) ++ "," ++
  show(eff_len[p]) ++ "," ++
  show(eff_wid[p]) ++ "," ++
  show(hgt[p]) ++ "\n"
  | p in BOXES
];