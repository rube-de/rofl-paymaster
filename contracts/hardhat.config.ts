import { HardhatUserConfig } from "hardhat/config";
import "@nomicfoundation/hardhat-toolbox";

const accounts = process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : {
  mnemonic: "test test test test test test test test test test test junk",
  path: "m/44'/60'/0'/0",
  initialIndex: 0,
  count: 20,
  passphrase: "",
};

const config: HardhatUserConfig = {
  networks: {
    hardhat: {
      forking: {
        url: `https://base-mainnet.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY}`,
        enabled: !!process.env.ALCHEMY_API_KEY
      }
    },
    "sapphire-localnet": { // Sapphire localnet docker
      url: "http://localhost:8545",
      chainId: 0x5afd,
      accounts,
    },    
    baseMainnet: {
      url: `https://base-mainnet.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY}`,
      accounts,
      chainId: 8453
    },
    baseSepolia: {
      url: process.env.BASE_SEPOLIA_RPC || "https://sepolia.base.org",
      accounts,
      chainId: 84532
    },
    sapphireTestnet: {
      url: process.env.SAPPHIRE_TESTNET_RPC || "https://testnet.sapphire.oasis.dev",
      accounts,
      chainId: 23295
    }
  },
  solidity: {
    version: "0.8.28",
    settings: {
      optimizer: {
        enabled: true,
      },
      viaIR: true,
    },
  },
};

export default config;
