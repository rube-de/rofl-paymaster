import { task } from "hardhat/config";
import { HardhatRuntimeEnvironment } from "hardhat/types";

task("deploy:mock-oracle", "Deploy MockROFLPriceOracle and optionally wire to CrossChainPaymaster")
  .addOptionalParam("tokens", "Comma-separated token addresses to register (optional)")
  .addOptionalParam("decimals", "Comma-separated decimals matching tokens (optional)")
  .addOptionalParam("paymaster", "CrossChainPaymaster proxy address to set oracle on (optional)")
  .setAction(async (args: { tokens?: string; decimals?: string; paymaster?: string }, hre: HardhatRuntimeEnvironment) => {
    const { ethers } = hre;

    console.log("Network:", hre.network.name);

    // 1) Deploy the mock oracle
    const Mock = await ethers.getContractFactory("MockROFLPriceOracle");
    const mock = await Mock.deploy();
    await mock.waitForDeployment();
    const mockAddress = await mock.getAddress();
    console.log("MockROFLPriceOracle deployed at:", mockAddress);

    // 2) Optionally register token decimals via addTokenFeed
    if (args.tokens) {
      const tokens = args.tokens.split(",").map((s) => s.trim()).filter(Boolean);
      const decs = args.decimals ? args.decimals.split(",").map((s) => parseInt(s.trim(), 10)) : [];
      if (decs.length > 0 && decs.length !== tokens.length) {
        throw new Error("decimals length must match tokens length when provided");
      }
      console.log(`Registering ${tokens.length} token feed(s) at 1:1 price...`);
      for (let i = 0; i < tokens.length; i++) {
        const token = tokens[i];
        const decimals = decs.length ? decs[i] : 18;
        const tx = await mock.addTokenFeed(token, ethers.parseUnits("1", 18), decimals);
        console.log(`  addTokenFeed(${token}, 1e18, ${decimals}) ->`, tx.hash);
        await tx.wait();
      }
    }

    // 3) Optionally wire into CrossChainPaymaster
    if (args.paymaster) {
      console.log("Setting CrossChainPaymaster oracle to:", mockAddress);
      const paymaster = await ethers.getContractAt("CrossChainPaymaster", args.paymaster);
      const tx = await paymaster.setPriceOracle(mockAddress);
      console.log("  setPriceOracle tx:", tx.hash);
      await tx.wait();
      console.log("✅ CrossChainPaymaster oracle updated");
    }

    console.log("\nDone.");
  });

