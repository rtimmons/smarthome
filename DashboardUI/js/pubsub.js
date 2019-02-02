// TODO: not used yet

var isFunc = function() {};

class PubSub {

  constructor(args) {
    this.topics = {'*': []};
    this.globals = {};
  }

  setGlobal(k, v) {
    this.globals[k] = v;
  }

  subscribe(topics, callback) {
    topics = typeof topics === 'string' ? [topics] : topics;
    for (var k in topics) {
      var topic = topics[k];
      this.topics[topic] = this.topics[topic] || [];
      if (typeof callback === typeof isFunc) {
        callback = {
          onMessage: callback,
        };
      }
      this.topics[topic].push(callback);      
    }
  }

  submit(topic, event) {
    var listeners = this.topics[topic] || [];
    if ( topic !== '*') {
      listeners.concat(this.topics['*']);
    }
    for(let k in listeners) {
      let listener = listeners[k];
      var toSubmit = {
        Topic: topic,
        Event: event,
        Globals: this.globals,
        Submitted: new Date(),
      };
      setTimeout(function(){
        listener.onMessage(toSubmit);
      }, 0); 
    }
  }

}
