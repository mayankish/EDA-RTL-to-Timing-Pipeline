// Technology-mapped netlist — module: full_adder_carry
// CLOCK: CLK period=200
module full_adder_carry (A, B, Cin, CARRY);
  input  A;
  input  B;
  input  Cin;
  output CARRY;
  wire   AND_t01, AND_t12, AND_t23, OR_final4;
  AND2 AND_t0_g1 (AND_t01, B, Cin);
  AND2 AND_t1_g1 (AND_t12, A, Cin);
  AND2 AND_t2_g1 (AND_t23, A, B);
  OR2 OR_final_g1 (OR_final4, AND_t01, AND_t12);
  OR2 OR_final_g2 (CARRY, OR_final4, AND_t23);
endmodule