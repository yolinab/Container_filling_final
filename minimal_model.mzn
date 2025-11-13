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


% --------------------
% DECISION VARIABLES
% --------------------

array[BOXES] of var 0..W: x;       % x-position
array[BOXES] of var 0..L: y;       % y-position
array[BOXES] of var 0..H: z;       % z-position

array[BOXES] of var 0..1: rot;     % 0 = normal, 1 = swapped rotation

array[BOXES] of var int: eff_len;  % effective length
array[BOXES] of var int: eff_wid;  % effective width


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
% NO OVERLAP (core logic)
% --------------------

constraint forall(p, q in BOXES where p < q)(
    (x[p] + eff_wid[p] <= x[q]) \/
    (x[q] + eff_wid[q] <= x[p]) \/
    (y[p] + eff_len[p] <= y[q]) \/
    (y[q] + eff_len[q] <= y[p]) \/
    (z[p] + hgt[p]     <= z[q]) \/
    (z[q] + hgt[q]     <= z[p])
);


% --------------------
% Just ask for ANY valid arrangement
% --------------------

solve satisfy;

output [
  "Box " ++ show(p)
  ++ ": x=" ++ show(x[p])
  ++ ", y=" ++ show(y[p])
  ++ ", z=" ++ show(z[p])
  ++ ", rot=" ++ show(rot[p])
  ++ "\n"
  | p in BOXES
];

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