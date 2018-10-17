const Voting = artifacts.require('./Voting.sol');
const Helper = artifacts.require('./Helper.sol');
const Ranking = artifacts.require('./Ranking.sol');

module.exports = (deployer) => {
  // deploy helper
  deployer.deploy(Helper);

  // link helper
  deployer.link(Helper, Ranking);

  // link helper
  deployer.link(Helper, Voting);
};