// Technology-mapped netlist — module: full_adder_sum
// CLOCK: CLK period=200
module full_adder_sum (A, B, Cin, SUM);
  input  A;
  input  B;
  input  Cin;
  output SUM;
  wire   AND_t03, AND_t04, AND_t17, AND_t18, AND_t211, AND_t212, AND_t313, AND_t314, OR_final15, OR_final16, inv1, inv10, inv2, inv5, inv6, inv9;
  INV INV_A_inv1 (inv1, A);
  INV INV_B_inv2 (inv2, B);
  AND2 AND_t0_g1 (AND_t03, inv1, inv2);
  AND2 AND_t0_g2 (AND_t04, AND_t03, Cin);
  INV INV_A_inv5 (inv5, A);
  INV INV_Cin_inv6 (inv6, Cin);
  AND2 AND_t1_g1 (AND_t17, inv5, B);
  AND2 AND_t1_g2 (AND_t18, AND_t17, inv6);
  INV INV_B_inv9 (inv9, B);
  INV INV_Cin_inv10 (inv10, Cin);
  AND2 AND_t2_g1 (AND_t211, A, inv9);
  AND2 AND_t2_g2 (AND_t212, AND_t211, inv10);
  AND2 AND_t3_g1 (AND_t313, A, B);
  AND2 AND_t3_g2 (AND_t314, AND_t313, Cin);
  OR2 OR_final_g1 (OR_final15, AND_t04, AND_t18);
  OR2 OR_final_g2 (OR_final16, AND_t212, AND_t314);
  OR2 OR_final_g3 (SUM, OR_final15, OR_final16);
endmodule