/**
 * JavaScript Synthetic Parser & Resolution Fixture
 * Covers 5 required constructs for LFCG extraction and resolution:
 * 1. ES module calls
 * 2. CommonJS imports
 * 3. Object methods
 * 4. Arrow functions
 * 5. Dynamic property calls
 */

// 1. ES module imports
import { formatString, parseConfig } from './esm_utils.js';

// 2. CommonJS require imports
const path = require('path');
const { readFileSync } = require('fs');

// 4. Arrow functions
const sanitizeInput = (text) => {
    return text.trim();
};

const buildEnvelope = (payload) => {
    return { data: sanitizeInput(payload) };
};

// 3. Object methods (prototype & literal methods)
const apiService = {
    apiKey: 'secret',
    validateKey(key) {
        return this.apiKey === key;
    },
    dispatchRequest(endpoint) {
        return `dispatched:${endpoint}`;
    }
};

function LegacyClass(prefix) {
    this.prefix = prefix;
}
LegacyClass.prototype.execute = function(val) {
    return this.prefix + ":" + val;
};

// Callers:

// 1. ES module calls
function callerEsModuleCalls() {
    const formatted = formatString("hello");
    const config = parseConfig("{}");
    return [formatted, config];
}

// 2. CommonJS calls
function callerCommonJsCalls() {
    const fullPath = path.resolve("root", "dir");
    const content = readFileSync(fullPath, "utf-8");
    return content;
}

// 3. Object methods
function callerObjectMethods() {
    const isValid = apiService.validateKey("secret");
    const inst = new LegacyClass("test");
    const res = inst.execute("data");
    return [isValid, res];
}

// 4. Arrow function calls
function callerArrowCalls() {
    return buildEnvelope(" raw string ");
}

// 5. Dynamic property calls
function callerDynamicPropertyCalls(obj, methodName, arg) {
    // Dynamic call syntax obj[methodName](arg)
    const result = obj[methodName](arg);
    return result;
}

module.exports = {
    callerEsModuleCalls,
    callerCommonJsCalls,
    callerObjectMethods,
    callerArrowCalls,
    callerDynamicPropertyCalls,
};

