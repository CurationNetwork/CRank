const Voting = artifacts.require('./VotingPoll.sol');
const AttributeStore = artifacts.require('attrstore/AttributeStore.sol');
const Helper = artifacts.require('./Helper.sol');
const Ranking = artifacts.require('./Ranking.sol');

module.exports = (deployer) => {
  // deploy libraries
  deployer.deploy(AttributeStore);

  // link libraries
  deployer.link(AttributeStore, Voting);

  // deploy helper
  deployer.deploy(Helper);

  // link helper
  deployer.link(Helper, Ranking);

};