const HDWalletProvider = require("truffle-hdwallet-provider");
const HDWalletProviderPK = require("truffle-hdwallet-provider-privkey");

module.exports = {
  networks: {
    development: {
      host: "localhost",
      port: 8545,
      network_id: "*", // Match any network id
      gas: 7007233,
    },

    rinkeby: {
      network_id: 4,
      gas: 7000000,
      gasPrice: 556250000000,
      provider: function () {
          return new HDWalletProviderPK([process.env.PRIVKEY], "http://10.100.11.24:8545")
      },
      from: "0x49d22f8740d6f08b3235ace9a90648b206962cbd",
    },

    rinkeby_infura: {
      provider: function() {
        return new HDWalletProvider(process.env.INFURA_MNEMO, "https://rinkeby.infura.io/v5/" + process.env.INFURA_APIKEY)
      },
      network_id: 4,
      gas: 7000000,
  //    gas: 4612388 // Gas limit used for deploys
    },

    // geth --testnet --rpc console --port 30304 --rpcport 8547 --wsport 8548 --fast --bootnodes 'enode://20c9ad97c081d63397d7b685a412227a40e23c8bdc6688c6f37e97cfbc22d2b4d1db1510d8f61e6a8866ad7f0e17c02b14182d37ea7c3c8b9c2683aeb6b733a1@52.169.14.227:30303,enode://6ce05930c72abc632c58e2e4324f7c7ea478cec0ed4fa2528982cf34483094e9cbc9216e7aa349691242576d552a2a56aaeae426c5303ded677ce455ba1acd9d@13.84.180.240:30303'
    ropsten: {  // testnet
      host: "localhost",
      port: 8547,
      network_id: 3
    },

    // geth --rpcport 8549 --wsport 8550 --rpc console --fast
    mainnet: {
      host: "localhost",
      port: 8549,
      network_id: 1,
      gasPrice: 22000000000
    }
  }
};
