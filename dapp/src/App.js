import React, { Component } from 'react';
import logo from './logo.svg';
import './App.css';

import Web3 from 'web3';

class App extends Component {
  render() {

	let web3 = new Web3('http://myhost:9545');
	console.log(web3);
	contract = 0xF12b5dd4EAD5F743C6BaA640B0216200e89B60Da
	return (
	<div className="App">
        <header className="App-header">
          <img src={logo} className="App-logo" alt="logo" />
          <h1 className="App-title">Welcome to React</h1>
        </header>
	<h1>s</h1>
        <p className="App-intro">
          To get started, edit <code>src/App.js</code> and save to reload.
        </p>
      </div>
    );
  }
}

export default App;
