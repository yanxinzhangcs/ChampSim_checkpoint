// File contains a signed and unsigned saturating counter class

#ifndef __SATURATING_COUNTER_CLASS__
#define __SATURATING_COUNTER_CLASS__

#include <limits>
#include <cstdint>

template <unsigned Bits>
class UnsignedSatCounter {
    static_assert(Bits > 0 && Bits <= 32);

    using StorageType = std::conditional_t<
        (Bits <= 8), uint8_t,
        std::conditional_t<
            (Bits <= 16), uint16_t,
            uint32_t
        >
    >;
    StorageType value;

public:
    static constexpr StorageType MAX_VALUE = (uint64_t(1) << Bits) - 1;
    static constexpr uint8_t bits = Bits;

    UnsignedSatCounter() : value(0) {}
    explicit UnsignedSatCounter(StorageType initial) : value(initial > MAX_VALUE ? MAX_VALUE : initial) {}

    void increment() {
        if (value < MAX_VALUE) {
            ++value;
        }
    }

    void decrement() {
        if (value > 0) {
            --value;
        }
    }

    void reset() {
        value = 0;
    }

    void set(StorageType val) {
        value = (val > MAX_VALUE) ? MAX_VALUE : val;
    }

    StorageType get() const {
        return value;
    }

    uint8_t MSB() const {
        return value >> (Bits - 1);
    }

    void setHalfway() { // Rounds down
        value = MAX_VALUE >> 1;
    }

    bool isMax() const {
        return value == MAX_VALUE;
    }


    // Comparison operators
    bool operator==(const UnsignedSatCounter& other) const { return value == other.value; }
    bool operator!=(const UnsignedSatCounter& other) const { return value != other.value; }
    bool operator<(const UnsignedSatCounter& other) const { return value < other.value; }
    bool operator>(const UnsignedSatCounter& other) const { return value > other.value; }
    bool operator<=(const UnsignedSatCounter& other) const { return value <= other.value; }
    bool operator>=(const UnsignedSatCounter& other) const { return value >= other.value; }

    // Increment and decrement operators
    UnsignedSatCounter& operator++() { // Prefix ++
        increment();
        return *this;
    }

    UnsignedSatCounter operator++(int) { // Postfix ++
        UnsignedSatCounter temp = *this;
        increment();
        return temp;
    }

    UnsignedSatCounter& operator--() { // Prefix --
        decrement();
        return *this;
    }

    UnsignedSatCounter operator--(int) { // Postfix --
        UnsignedSatCounter temp = *this;
        decrement();
        return temp;
    }

    // Addition and subtraction assignment operators
    UnsignedSatCounter& operator+=(StorageType amount) {
        value = (value + amount > MAX_VALUE) ? MAX_VALUE : value + amount;
        return *this;
    }

    UnsignedSatCounter& operator-=(StorageType amount) {
        value = (value < amount) ? 0 : value - amount;
        return *this;
    }

    // Arithmetic operators
    UnsignedSatCounter operator+(const UnsignedSatCounter& other) const {
        return UnsignedSatCounter((value + other.value > MAX_VALUE) ? MAX_VALUE : value + other.value);
    }

    UnsignedSatCounter operator-(const UnsignedSatCounter& other) const {
        return UnsignedSatCounter((value < other.value) ? 0 : value - other.value);
    }

    // Allow interaction with regular integers
    friend StorageType& operator+=(StorageType& lhs, const UnsignedSatCounter& rhs) {
        lhs += rhs.value;
        return lhs;
    }

    friend StorageType operator+(StorageType lhs, const UnsignedSatCounter& rhs) {
        return lhs + rhs.value;
    }

    friend StorageType operator-(StorageType lhs, const UnsignedSatCounter& rhs) {
        return lhs - rhs.value;
    }

    friend StorageType& operator-=(StorageType& lhs, const UnsignedSatCounter& rhs) {
        lhs -= rhs.value;
        return lhs;
    }

    UnsignedSatCounter& operator>>=(StorageType amount) {
        if (amount >= Bits) {
            value = 0;
        } else {
            value >>= amount;
        }
        return *this;
    }
};



template <unsigned Bits>
class SignedSatCounter {
    static_assert(Bits > 0 && Bits <= 32);

    using StorageType = std::conditional_t<
        (Bits <= 8), int8_t,
        std::conditional_t<
            (Bits <= 16), int16_t,
            int32_t
        >
    >;

    static constexpr StorageType MIN_VALUE = (Bits == 32) ? std::numeric_limits<int32_t>::min() : -(1 << (Bits - 1));
    static constexpr StorageType MAX_VALUE = (Bits == 32) ? std::numeric_limits<int32_t>::max() : (1 << (Bits - 1)) - 1;

    StorageType value;

public:
    static constexpr uint8_t bits = Bits;

    SignedSatCounter() : value(0) {}
    explicit SignedSatCounter(StorageType initial) 
        : value((initial > MAX_VALUE) ? MAX_VALUE : (initial < MIN_VALUE) ? MIN_VALUE : initial) {}

    void increment() {
        if (value < MAX_VALUE) {
            ++value;
        }
    }

    void decrement() {
        if (value > MIN_VALUE) {
            --value;
        }
    }

    void reset() {
        value = 0;
    }

    void set(StorageType val) {
        value = (val > MAX_VALUE) ? MAX_VALUE : (val < MIN_VALUE) ? MIN_VALUE : val;
    }

    StorageType get() const {
        return value;
    }

    int8_t MSB() const {
        return (value < 0) ? 1 : 0;
    }

    void setHalfway() { // Rounds towards zero
        value = 0;
    }

    bool isMax() const {
        return value == MAX_VALUE;
    }
    
    bool isMin() const {
        return value == MIN_VALUE;
    }

    // Comparison operators
    bool operator==(const SignedSatCounter& other) const { return value == other.value; }
    bool operator!=(const SignedSatCounter& other) const { return value != other.value; }
    bool operator<(const SignedSatCounter& other) const { return value < other.value; }
    bool operator>(const SignedSatCounter& other) const { return value > other.value; }
    bool operator<=(const SignedSatCounter& other) const { return value <= other.value; }
    bool operator>=(const SignedSatCounter& other) const { return value >= other.value; }

    // Increment and decrement operators
    SignedSatCounter& operator++() { increment(); return *this; }
    SignedSatCounter operator++(int) { SignedSatCounter temp = *this; increment(); return temp; }
    SignedSatCounter& operator--() { decrement(); return *this; }
    SignedSatCounter operator--(int) { SignedSatCounter temp = *this; decrement(); return temp; }

    // Addition and subtraction assignment operators
    SignedSatCounter& operator+=(StorageType amount) {
        set(value + amount);
        return *this;
    }

    SignedSatCounter& operator-=(StorageType amount) {
        set(value - amount);
        return *this;
    }

    // Arithmetic operators
    SignedSatCounter operator+(const SignedSatCounter& other) const {
        return SignedSatCounter(value + other.value);
    }

    SignedSatCounter operator-(const SignedSatCounter& other) const {
        return SignedSatCounter(value - other.value);
    }

    // Allow interaction with regular integers
    friend StorageType& operator+=(StorageType& lhs, const SignedSatCounter& rhs) {
        lhs += rhs.value;
        return lhs;
    }

    friend StorageType operator+(StorageType lhs, const SignedSatCounter& rhs) {
        return lhs + rhs.value;
    }

    friend StorageType operator-(StorageType lhs, const SignedSatCounter& rhs) {
        return lhs - rhs.value;
    }

    friend StorageType& operator-=(StorageType& lhs, const SignedSatCounter& rhs) {
        lhs -= rhs.value;
        return lhs;
    }

    SignedSatCounter& operator>>=(StorageType amount) {
        if (amount >= Bits) {
            value = (value < 0) ? MIN_VALUE : 0;
        } else {
            value >>= amount;
        }
        return *this;
    }

    operator StorageType() const { return value; }
};

#endif // End of __SATURATING_COUNTER_CLASS__
