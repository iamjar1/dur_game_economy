# AI Disclosure

## Tools Used

### Claude (Anthropic)
- **Usage:** Primary AI assistant for architecture design, code generation, and documentation
- **Scope:** 
  - Database schema design (SQLite with WAL mode)
  - Idempotency strategy (SHA-256 keys with 48h retention)
  - Service layer implementation (credit, purchase, claim)
  - FastAPI endpoints with Pydantic validation
  - Test suite (concurrency, idempotency, validation)
  - Docker configuration
  - DESIGN.md and RESILIENCE.md documentation

## What I Did Myself

Coding but assisted. Learned alot in regards to the failsafe checks and fallbacks to go during crashes. Learned Idempotency and Atomicity for safer crash responses. 

## AI Limitations

1. **No runtime execution** - AI cannot run code or verify it works in practice
2. **No environment knowledge** - AI doesn't know local Docker/Python setup
3. **No integration testing** - Cannot test actual Docker builds or crash scenarios
4. **Requires human verification** - All code must be tested by the developer

## Integrity Statement

I have reviewed all AI-generated code and documentation. I understand the implementation and can explain every design decision. The code represents my understanding of the requirements and my architectural choices.

I have not:
- Submitted AI-generated work without review
- Claimed capabilities the code doesn't implement
- Misrepresented my contribution
