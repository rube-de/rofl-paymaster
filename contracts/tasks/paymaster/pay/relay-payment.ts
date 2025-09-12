import { task } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";
import * as fs from "fs";

// Proof tuple format saved by pay:generate-proof
// [chainId, blockNumber, blockHeader, ancestralBlockNumber, ancestralBlockHeaders, receiptProof, transactionIndex, logIndex]
type ProofTuple = [number, number, string, number, string[], string[], string, number];

task("pay:relay", "Relay PaymentInitiated proof to CrossChainPaymaster on Sapphire")
  .addParam("proof", "Proof data (JSON file path or inline JSON string)")
  .addParam("paymaster", "CrossChainPaymaster proxy address on Sapphire")
  .setAction(async (args, hre: HardhatRuntimeEnvironment) => {
    const { ethers } = hre;

    console.log("🌉 Relaying payment to CrossChainPaymaster");
    console.log("Paymaster:", args.paymaster);
    console.log("Network:", hre.network.name);

    try {
      // Load proof
      let proof: ProofTuple;
      if (String(args.proof).trim().startsWith("{")) {
        console.log("📄 Parsing inline proof JSON...");
        proof = JSON.parse(args.proof);
      } else {
        console.log("📁 Reading proof file:", args.proof);
        if (!fs.existsSync(args.proof)) throw new Error(`Proof file not found: ${args.proof}`);
        const raw = fs.readFileSync(args.proof, "utf8");
        proof = JSON.parse(raw);
      }

      // Validate basic structure
      if (!Array.isArray(proof) || proof.length !== 8) {
        throw new Error(
          "Invalid proof format: expected array [chainId, blockNumber, blockHeader, ancestralBlockNumber, ancestralBlockHeaders, receiptProof, transactionIndex, logIndex]"
        );
      }

      const [chainId, blockNumber, blockHeader, ancestralBlockNumber, ancestralBlockHeaders, receiptProofArray, transactionIndex, logIndex] = proof;
      if (typeof chainId !== "number" || typeof blockNumber !== "number" || typeof blockHeader !== "string") {
        throw new Error("Invalid types in proof: chainId, blockNumber must be numbers; blockHeader must be string");
      }
      if (!Array.isArray(ancestralBlockHeaders) || !Array.isArray(receiptProofArray)) {
        throw new Error("Invalid arrays in proof: ancestralBlockHeaders and receiptProof must be arrays");
      }
      if (typeof transactionIndex !== "string" || typeof logIndex !== "number") {
        throw new Error("Invalid types in proof: transactionIndex must be string; logIndex must be number");
      }

      console.log("  ✅ Proof validated");
      console.log("  Source Chain ID:", chainId);
      console.log("  Block Number:", blockNumber);
      console.log("  Log Index:", logIndex);
      console.log("  Receipt Proof Nodes:", receiptProofArray.length);

      // Connect to CrossChainPaymaster
      const paymaster = await ethers.getContractAt("CrossChainPaymaster", args.paymaster);

      // Compose ReceiptProof struct
      const receiptProof = {
        chainId,
        blockNumber,
        blockHeader,
        ancestralBlockNumber,
        ancestralBlockHeaders,
        receiptProof: receiptProofArray,
        transactionIndex,
        logIndex,
      };

      console.log("\n📤 Submitting to CrossChainPaymaster.processPaymentReceipt()...");
      console.log("  Caller must be roflOperator or owner");

      const tx = await paymaster.processPaymentReceipt(receiptProof);
      console.log("  tx:", tx.hash);
      console.log("⏳ Waiting for confirmation...");
      const rc = await tx.wait();

      if (rc?.status !== 1) throw new Error("Transaction failed");
      console.log("✅ Payment relayed successfully");
      console.log("  Block:", rc.blockNumber);
      console.log("  Gas used:", rc.gasUsed.toString());

      // Parse events
      const events = rc.logs
        .map((l) => {
          try {
            return paymaster.interface.parseLog(l);
          } catch {
            return null;
          }
        })
        .filter((e) => e !== null);

      for (const e of events) {
        if (e!.name === "PaymentProcessed") {
          console.log("\n🎉 PaymentProcessed:");
          console.log("  Payment ID:", e!.args.paymentId);
          console.log("  ROSE Amount:", e!.args.roseAmount.toString());
        }
      }

      return { txHash: tx.hash, blockNumber: rc.blockNumber };
    } catch (err: any) {
      console.error("❌ Relay failed:", err?.message || err);
      if (err?.message?.includes("NotOperatorOrOwner")) {
        console.log("\n💡 The caller must be roflOperator or owner on CrossChainPaymaster.");
      } else if (err?.message?.includes("ChainDisabled")) {
        console.log("\n💡 Enable the source chain in CrossChainPaymaster via configure:cross-chain-paymaster.");
      } else if (err?.message?.includes("VaultNotAuthorized")) {
        console.log("\n💡 Authorize the source PaymasterVault for this chain in CrossChainPaymaster.");
      } else if (err?.message?.includes("DuplicatePayment")) {
        console.log("\n💡 This paymentId was already processed. Each deposit can be redeemed once.");
      } else if (err?.message?.includes("DistributionLimitExceeded")) {
        console.log("\n💡 Increase distribution limits or try a smaller amount.");
      } else if (err?.message?.includes("InvalidEvent")) {
        console.log("\n💡 The proof doesn’t point to a PaymentInitiated event. Re-generate proof for the correct tx and log index.");
      }
      throw err;
    }
  });

