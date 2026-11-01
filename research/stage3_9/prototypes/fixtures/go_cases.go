package fixtures

import (
	"fmt"
	"strings"
	aliasjson "encoding/json"
)

// 1. Package-local function definitions
func LocalTargetGo(msg string) string {
	return "go:" + msg
}

func HelperProcess(val int) int {
	return val * 2
}

// 4. Interfaces
type Processor interface {
	ProcessData(input string) string
	Execute() error
}

type AlternateProcessor interface {
	ProcessData(input string) string
}

// 3. Receiver methods
type Engine struct {
	ID string
}

func (e *Engine) ProcessData(input string) string {
	return e.ID + ":" + input
}

func (e *Engine) InternalMethod() string {
	return "internal:" + e.ID
}

// 5. Ambiguous method names on different struct
type Reporter struct {
	Name string
}

func (r *Reporter) ProcessData(input string) string {
	return "report:" + r.Name + ":" + input
}

// Caller functions covering the cases:

// 1. Package-local calls
func CallerPackageLocal() string {
	res1 := LocalTargetGo("hello")
	res2 := HelperProcess(42)
	return fmt.Sprintf("%s:%d", res1, res2)
}

// 2. Imported package functions & aliases
func CallerImportedPackage(data []byte) (string, error) {
	upper := strings.ToUpper("test")
	var payload map[string]interface{}
	err := aliasjson.Unmarshal(data, &payload)
	return upper, err
}

// 3. Receiver method calls
func (e *Engine) CallerReceiverMethod() string {
	val := e.InternalMethod()
	return val
}

// 4. Interface dispatch (dynamic target)
func CallerInterfaceInvocation(p Processor, input string) string {
	// Call on interface: receiver type unknown at compile/parse time without type checker
	return p.ProcessData(input)
}

// 5. Ambiguous method call resolution site
func CallerAmbiguousDispatch(obj interface{ ProcessData(string) string }, input string) string {
	// Ambiguous between Engine.ProcessData and Reporter.ProcessData
	return obj.ProcessData(input)
}

