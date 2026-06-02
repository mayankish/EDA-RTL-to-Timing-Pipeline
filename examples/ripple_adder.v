// Gate-level netlist: 2-bit Ripple Carry Adder
// Inputs : A0, A1, B0, B1, Cin
// Outputs: S0, S1, Cout
//
// Timing annotations:
// CLOCK: CLK period=200
// INPUT_DELAY: A0=10 A1=10 B0=10 B1=10 Cin=10

module ripple_adder_2bit (S0, S1, Cout, A0, A1, B0, B1, Cin);
  input  A0, A1, B0, B1, Cin;
  output S0, S1, Cout;
  wire   xor1_out, and1_out, and2_out, or1_out, xor3_out, and3_out, and4_out;

  // Full adder bit 0 (LSB)
  // S0 = A0 XOR B0 XOR Cin
  XOR2 XOR_S0_1  (xor1_out, A0, B0);
  XOR2 XOR_S0_2  (S0,       xor1_out, Cin);

  // Carry out of bit 0
  // C0 = (A0 AND B0) OR (Cin AND (A0 XOR B0))
  AND2 AND_C0_1  (and1_out, A0, B0);
  AND2 AND_C0_2  (and2_out, Cin, xor1_out);
  OR2  OR_C0     (or1_out,  and1_out, and2_out);

  // Full adder bit 1 (MSB)
  // S1 = A1 XOR B1 XOR C0
  XOR2 XOR_S1_1  (xor3_out, A1, B1);
  XOR2 XOR_S1_2  (S1,       xor3_out, or1_out);

  // Carry out of bit 1
  AND2 AND_C1_1  (and3_out, A1, B1);
  AND2 AND_C1_2  (and4_out, or1_out, xor3_out);
  OR2  OR_Cout   (Cout,     and3_out, and4_out);

endmodule
